#!/usr/bin/env python3
"""
US Reports API - REST API for receiving and storing US (Ultrasound) reports

This API provides endpoints to:
- Receive US reports from external processing systems
- Store reports in PostgreSQL database (reports.us table)
- Query existing reports

Endpoints:
  POST /api/us/report - Submit a new US report
    POST /api/us/draft - Submit or update a draft US report
  GET /api/us/report/<mrn> - Get reports by MRN
  GET /api/us/report/<mrn>/<acc> - Get specific report by MRN and Accession
  GET /api/health - Health check endpoint

Database: PostgreSQL (qii database, reports.us table)
Port: 5667 (configurable)
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import logging
from datetime import datetime
import traceback
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'facundo',
    'password': 'qii123',
    'database': 'qii'
}


def get_db_connection():
    """
    Create and return a database connection.
    
    Returns:
        psycopg2.connection: Database connection object
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise


@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Health check endpoint to verify API and database connectivity.
    
    Returns:
        JSON response with status and database connection status
    """
    try:
        # Test database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.close()
        conn.close()
        
        return jsonify({
            'status': 'healthy',
            'service': 'US Reports API',
            'database': 'connected',
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'service': 'US Reports API',
            'database': 'disconnected',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 503


@app.route('/api/us/report', methods=['POST'])
def create_us_report():
    """
    Create a new US report in the database.
    
    Expected JSON payload:
    {
        "mrn": "patient_medical_record_number",
        "acc": "accession_number",  // optional
        "report": "report_text_content"
    }
    
    Returns:
        JSON response with created report GUID or error message
    """
    try:
        # Validate request content type
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), 400
        
        # Get JSON data
        data = request.get_json()
        
        # Validate required fields
        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is empty'
            }), 400
        
        mrn = data.get('mrn', '').strip()
        acc = data.get('acc', '').strip()
        report = data.get('report', '').strip()
        
        # Validate required fields
        if not mrn:
            return jsonify({
                'success': False,
                'error': 'Field "mrn" is required and cannot be empty'
            }), 400
        
        if not report:
            return jsonify({
                'success': False,
                'error': 'Field "report" is required and cannot be empty'
            }), 400
        
        # Connect to database
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Check if report already exists for this MRN and ACC
        if acc:
            cursor.execute("""
                SELECT guid, mrn, acc, createdon, updatedon
                FROM reports.us
                WHERE mrn = %s AND acc = %s
            """, (mrn, acc))
        else:
            cursor.execute("""
                SELECT guid, mrn, acc, createdon, updatedon
                FROM reports.us
                WHERE mrn = %s AND (acc IS NULL OR acc = '')
                ORDER BY createdon DESC
                LIMIT 1
            """, (mrn,))
        
        existing_report = cursor.fetchone()
        
        if existing_report:
            # Update existing report
            cursor.execute("""
                UPDATE reports.us
                SET report = %s,
                    updatedon = NOW()
                WHERE guid = %s
                RETURNING guid, mrn, acc, createdon, updatedon
            """, (report, existing_report['guid']))
            
            updated_report = cursor.fetchone()
            conn.commit()
            
            logger.info(f"✓ US Report UPDATED - MRN: {mrn}, ACC: {acc}, GUID: {updated_report['guid']}")
            
            cursor.close()
            conn.close()
            
            # Forward to us_ai table via qiiextension_backend API
            try:
                ai_payload = {
                    'mrn': mrn,
                    'acc': acc if acc else '',
                    'report': report
                }
                ai_response = requests.post(
                    'http://localhost:5555/api/us/report',
                    json=ai_payload,
                    timeout=10
                )
                logger.info(f"✓ Forwarded to us_ai table - Status: {ai_response.status_code}")
            except Exception as forward_error:
                logger.warning(f"⚠ Failed to forward to us_ai table: {forward_error}")
            
            return jsonify({
                'success': True,
                'action': 'updated',
                'guid': updated_report['guid'],
                'mrn': updated_report['mrn'],
                'acc': updated_report['acc'],
                'createdon': updated_report['createdon'].isoformat() if updated_report['createdon'] else None,
                'updatedon': updated_report['updatedon'].isoformat() if updated_report['updatedon'] else None,
                'message': 'US report updated successfully'
            }), 200
        else:
            # Insert new report
            cursor.execute("""
                INSERT INTO reports.us (mrn, acc, report, createdon, updatedon)
                VALUES (%s, %s, %s, NOW(), NOW())
                RETURNING guid, mrn, acc, createdon, updatedon
            """, (mrn, acc if acc else None, report))
            
            new_report = cursor.fetchone()
            conn.commit()
            
            logger.info(f"✓ US Report CREATED - MRN: {mrn}, ACC: {acc}, GUID: {new_report['guid']}")
            
            cursor.close()
            conn.close()
            
            # Forward to us_ai table via qiiextension_backend API
            try:
                ai_payload = {
                    'mrn': mrn,
                    'acc': acc if acc else '',
                    'report': report
                }
                ai_response = requests.post(
                    'http://localhost:5555/api/us/report',
                    json=ai_payload,
                    timeout=10
                )
                logger.info(f"✓ Forwarded to us_ai table - Status: {ai_response.status_code}")
            except Exception as forward_error:
                logger.warning(f"⚠ Failed to forward to us_ai table: {forward_error}")
            
            return jsonify({
                'success': True,
                'action': 'created',
                'guid': new_report['guid'],
                'mrn': new_report['mrn'],
                'acc': new_report['acc'],
                'createdon': new_report['createdon'].isoformat() if new_report['createdon'] else None,
                'updatedon': new_report['updatedon'].isoformat() if new_report['updatedon'] else None,
                'message': 'US report created successfully'
            }), 201
        
    except psycopg2.Error as db_error:
        logger.error(f"✗ Database error: {db_error}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'details': str(db_error)
        }), 500
        
    except Exception as e:
        logger.error(f"✗ Error creating US report: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/us/draft', methods=['POST'])
def create_us_draft():
    """
    Create or update a US draft report in reports.drafts.

    Expected JSON payload:
    {
        "mrn": "patient_medical_record_number",
        "acc": "accession_number",  // optional
        "report": "report_text_content",
        "notes": "optional_notes",
        "author": "optional_author"
    }

    Returns:
        JSON response with created/updated draft GUID or error message
    """
    try:
        if not request.is_json:
            return jsonify({
                'success': False,
                'error': 'Content-Type must be application/json'
            }), 400

        data = request.get_json()

        if not data:
            return jsonify({
                'success': False,
                'error': 'Request body is empty'
            }), 400

        mrn = data.get('mrn', '').strip()
        acc = data.get('acc', '').strip()
        report = data.get('report', '').strip()

        if 'notes' in data and data.get('notes') is not None and not isinstance(data.get('notes'), str):
            return jsonify({
                'success': False,
                'error': 'Field "notes" must be a string or null'
            }), 400

        if 'author' in data and data.get('author') is not None and not isinstance(data.get('author'), str):
            return jsonify({
                'success': False,
                'error': 'Field "author" must be a string or null'
            }), 400

        notes = data.get('notes')
        author = data.get('author')
        notes = notes.strip() if isinstance(notes, str) and notes.strip() else None
        author = author.strip() if isinstance(author, str) and author.strip() else None

        if not mrn:
            return jsonify({
                'success': False,
                'error': 'Field "mrn" is required and cannot be empty'
            }), 400

        if not report:
            return jsonify({
                'success': False,
                'error': 'Field "report" is required and cannot be empty'
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        if acc:
            cursor.execute("""
                SELECT guid, mrn, acc, notes, author, createdon, updatedon
                FROM reports.drafts
                WHERE mrn = %s AND acc = %s
            """, (mrn, acc))
        else:
            cursor.execute("""
                SELECT guid, mrn, acc, notes, author, createdon, updatedon
                FROM reports.drafts
                WHERE mrn = %s AND (acc IS NULL OR acc = '')
                ORDER BY createdon DESC
                LIMIT 1
            """, (mrn,))

        existing_draft = cursor.fetchone()

        if existing_draft:
            cursor.execute("""
                UPDATE reports.drafts
                SET report = %s,
                    notes = %s,
                    author = %s,
                    updatedon = NOW()
                WHERE guid = %s
                RETURNING guid, mrn, acc, notes, author, createdon, updatedon
            """, (report, notes, author, existing_draft['guid']))

            updated_draft = cursor.fetchone()
            conn.commit()

            logger.info(f"✓ US Draft UPDATED - MRN: {mrn}, ACC: {acc}, GUID: {updated_draft['guid']}")

            cursor.close()
            conn.close()

            # Forward to AI endpoint
            try:
                ai_payload = {
                    'mrn': mrn,
                    'acc': acc if acc else '',
                    'report': report,
                    'author': author,
                    'notes': notes
                }
                ai_response = requests.post(
                    'https://ai.qiitools.com/api/upload-report',
                    json=ai_payload,
                    timeout=10
                )
                logger.info(f"✓ Forwarded to AI endpoint - Status: {ai_response.status_code}")
            except Exception as forward_error:
                logger.warning(f"⚠ Failed to forward to AI endpoint: {forward_error}")

            return jsonify({
                'success': True,
                'action': 'updated',
                'guid': updated_draft['guid'],
                'mrn': updated_draft['mrn'],
                'acc': updated_draft['acc'],
                'notes': updated_draft['notes'],
                'author': updated_draft['author'],
                'createdon': updated_draft['createdon'].isoformat() if updated_draft['createdon'] else None,
                'updatedon': updated_draft['updatedon'].isoformat() if updated_draft['updatedon'] else None,
                'message': 'US draft updated successfully'
            }), 200

        cursor.execute("""
            INSERT INTO reports.drafts (mrn, acc, report, notes, author, createdon, updatedon)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            RETURNING guid, mrn, acc, notes, author, createdon, updatedon
        """, (mrn, acc if acc else None, report, notes, author))

        new_draft = cursor.fetchone()
        conn.commit()

        logger.info(f"✓ US Draft CREATED - MRN: {mrn}, ACC: {acc}, GUID: {new_draft['guid']}")

        cursor.close()
        conn.close()

        # Forward to AI endpoint
        try:
            ai_payload = {
                'mrn': mrn,
                'acc': acc if acc else '',
                'report': report,
                'author': author,
                'notes': notes
            }
            ai_response = requests.post(
                'https://ai.qiitools.com/api/upload-report',
                json=ai_payload,
                timeout=10
            )
            logger.info(f"✓ Forwarded to AI endpoint - Status: {ai_response.status_code}")
        except Exception as forward_error:
            logger.warning(f"⚠ Failed to forward to AI endpoint: {forward_error}")

        return jsonify({
            'success': True,
            'action': 'created',
            'guid': new_draft['guid'],
            'mrn': new_draft['mrn'],
            'acc': new_draft['acc'],
            'notes': new_draft['notes'],
            'author': new_draft['author'],
            'createdon': new_draft['createdon'].isoformat() if new_draft['createdon'] else None,
            'updatedon': new_draft['updatedon'].isoformat() if new_draft['updatedon'] else None,
            'message': 'US draft created successfully'
        }), 201

    except psycopg2.Error as db_error:
        logger.error(f"✗ Database error in drafts endpoint: {db_error}")
        return jsonify({
            'success': False,
            'error': 'Database error',
            'details': str(db_error)
        }), 500

    except Exception as e:
        logger.error(f"✗ Error creating US draft: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': 'Internal server error',
            'details': str(e)
        }), 500


@app.route('/api/us/report/<mrn>', methods=['GET'])
def get_reports_by_mrn(mrn):
    """
    Get all US reports for a specific MRN.
    
    Args:
        mrn: Medical Record Number
        
    Returns:
        JSON array of reports or error message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT guid, mrn, acc, report, createdon, updatedon
            FROM reports.us
            WHERE mrn = %s
            ORDER BY createdon DESC
        """, (mrn,))
        
        reports = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Convert datetime objects to ISO format
        for report in reports:
            if report['createdon']:
                report['createdon'] = report['createdon'].isoformat()
            if report['updatedon']:
                report['updatedon'] = report['updatedon'].isoformat()
        
        logger.info(f"✓ Retrieved {len(reports)} report(s) for MRN: {mrn}")
        
        return jsonify({
            'success': True,
            'mrn': mrn,
            'count': len(reports),
            'reports': reports
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error retrieving reports for MRN {mrn}: {e}")
        return jsonify({
            'success': False,
            'error': 'Error retrieving reports',
            'details': str(e)
        }), 500


@app.route('/api/us/report/<mrn>/<acc>', methods=['GET'])
def get_report_by_mrn_acc(mrn, acc):
    """
    Get a specific US report by MRN and Accession Number.
    
    Args:
        mrn: Medical Record Number
        acc: Accession Number
        
    Returns:
        JSON report object or error message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT guid, mrn, acc, report, createdon, updatedon
            FROM reports.us
            WHERE mrn = %s AND acc = %s
        """, (mrn, acc))
        
        report = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not report:
            logger.info(f"ℹ No report found for MRN: {mrn}, ACC: {acc}")
            return jsonify({
                'success': False,
                'error': 'Report not found',
                'mrn': mrn,
                'acc': acc
            }), 404
        
        # Convert datetime objects to ISO format
        if report['createdon']:
            report['createdon'] = report['createdon'].isoformat()
        if report['updatedon']:
            report['updatedon'] = report['updatedon'].isoformat()
        
        logger.info(f"✓ Retrieved report for MRN: {mrn}, ACC: {acc}")
        
        return jsonify({
            'success': True,
            'report': report
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error retrieving report for MRN {mrn}, ACC {acc}: {e}")
        return jsonify({
            'success': False,
            'error': 'Error retrieving report',
            'details': str(e)
        }), 500


@app.route('/api/us/stats', methods=['GET'])
def get_stats():
    """
    Get statistics about US reports in the database.
    
    Returns:
        JSON with total count, recent reports count, etc.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Total reports
        cursor.execute("SELECT COUNT(*) as total FROM reports.us")
        total = cursor.fetchone()['total']
        
        # Reports today
        cursor.execute("""
            SELECT COUNT(*) as today
            FROM reports.us
            WHERE DATE(createdon) = CURRENT_DATE
        """)
        today = cursor.fetchone()['today']
        
        # Reports this week
        cursor.execute("""
            SELECT COUNT(*) as week
            FROM reports.us
            WHERE createdon >= CURRENT_DATE - INTERVAL '7 days'
        """)
        week = cursor.fetchone()['week']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_reports': total,
                'reports_today': today,
                'reports_this_week': week
            },
            'timestamp': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"✗ Error retrieving stats: {e}")
        return jsonify({
            'success': False,
            'error': 'Error retrieving statistics',
            'details': str(e)
        }), 500


@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'message': 'The requested endpoint does not exist'
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500


def main():
    """
    Start the US Reports API server.
    
    Listens on 0.0.0.0:5667 for incoming HTTP requests.
    """
    logger.info("=" * 70)
    logger.info("US Reports API Service")
    logger.info("=" * 70)
    logger.info(f"Database: {DB_CONFIG['database']}@{DB_CONFIG['host']}")
    logger.info(f"Server Address: 0.0.0.0:5667")
    logger.info("=" * 70)
    logger.info("Available endpoints:")
    logger.info("  POST   /api/us/report           - Create/Update US report")
    logger.info("  POST   /api/us/draft            - Create/Update US draft report")
    logger.info("  GET    /api/us/report/<mrn>     - Get reports by MRN")
    logger.info("  GET    /api/us/report/<mrn>/<acc> - Get specific report")
    logger.info("  GET    /api/us/stats            - Get statistics")
    logger.info("  GET    /api/health              - Health check")
    logger.info("=" * 70)
    logger.info("Starting server...")
    
    try:
        app.run(host='0.0.0.0', port=5667, debug=False)
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")


if __name__ == "__main__":
    main()
