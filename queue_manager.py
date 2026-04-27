#!/usr/bin/env python3
"""
Queue Manager para DICOM Receiver - Procesamiento Asíncrono
Gestiona pools de ThreadPoolExecutor para procesamiento en background de:
- Reenvío de imágenes US (Ultrasound)
- Procesamiento de estudios BD (Bone Density)
- Extracción de mapas de píxeles

Diseñado para respuesta inmediata en el handler C-STORE sin bloquear el gateway.
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from typing import Dict, Any, Callable, Optional
import atexit

logger = logging.getLogger(__name__)


class QueueManager:
    """
    Gestor centralizado de colas de procesamiento asíncrono.
    
    Mantiene tres pools de workers:
    - US forwarding: Reenvío de imágenes US a servidor AI
    - BD processing: Extracción y procesamiento de estudios de densitometría
    - Pixel extraction: Generación de mapas de píxeles JPEG
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa el gestor de colas con configuración personalizada.
        
        Args:
            config: Diccionario con configuración ASYNC_PROCESSING
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        
        # Colas para cada tipo de trabajo
        self.us_queue = Queue()
        self.bd_queue = Queue()
        self.pixel_queue = Queue()
        
        # Pools de workers
        us_workers = config.get('us_workers', 2)
        bd_workers = config.get('bd_workers', 4)
        pixel_workers = config.get('pixel_workers', 2)
        
        self.us_executor = ThreadPoolExecutor(
            max_workers=us_workers,
            thread_name_prefix='us_worker'
        ) if self.enabled else None
        
        self.bd_executor = ThreadPoolExecutor(
            max_workers=bd_workers,
            thread_name_prefix='bd_worker'
        ) if self.enabled else None
        
        self.pixel_executor = ThreadPoolExecutor(
            max_workers=pixel_workers,
            thread_name_prefix='pixel_worker'
        ) if self.enabled else None
        
        # Control de monitoreo
        self.monitor_interval = config.get('queue_monitor_interval', 30)
        self.stats_interval = config.get('stats_interval', 30)
        self.max_queue_size = config.get('max_queue_size', 1000)
        self.alert_threshold = config.get('alert_threshold', 800)
        self.degradation_threshold = config.get('degradation_threshold', 950)
        self.monitor_thread = None
        self.shutdown_flag = threading.Event()
        self.last_stats_time = time.time()
        
        # Contadores de estadísticas
        self.stats = {
            'us_submitted': 0,
            'us_completed': 0,
            'us_failed': 0,
            'bd_submitted': 0,
            'bd_completed': 0,
            'bd_failed': 0,
            'pixel_submitted': 0,
            'pixel_completed': 0,
            'pixel_failed': 0,
        }
        self.stats_lock = threading.Lock()
        
        # =====================================================================
        # DEFERRED PROCESSING: Prioridad en recepción, procesar después
        # =====================================================================
        self.defer_processing = config.get('defer_processing', False)
        self.study_completion_timeout = config.get('study_completion_timeout', 8)
        self.defer_check_interval = config.get('defer_check_interval', 3)
        
        # Diccionario de estudios activos: {study_uid: {'last_activity': timestamp, 'jobs': []}}
        self.active_studies = {}
        self.active_studies_lock = threading.Lock()
        
        # Thread para monitorear estudios completos
        self.defer_monitor_thread = None
        
        # Registrar shutdown handler
        atexit.register(self.shutdown)
        
        if self.enabled:
            mode_str = "DEFER (Recepción primero)" if self.defer_processing else "IMMEDIATE"
            logger.info(f"✓ QueueManager inicializado - US workers: {us_workers}, "
                       f"BD workers: {bd_workers}, Pixel workers: {pixel_workers}")
            logger.info(f"  Modo: {mode_str}")
            if self.defer_processing:
                logger.info(f"  Timeout de estudio completo: {self.study_completion_timeout}s")
            self._start_monitor()
            
            # Iniciar monitor de diferimiento si está habilitado
            if self.defer_processing:
                self._start_defer_monitor()
        else:
            logger.info("⚠️  QueueManager en modo DESHABILITADO - usando procesamiento síncrono")
    
    def _start_monitor(self):
        """Inicia thread de monitoreo de colas."""
        self.monitor_thread = threading.Thread(
            target=self._monitor_queues,
            name='queue_monitor',
            daemon=True
        )
        self.monitor_thread.start()
    
    def _start_defer_monitor(self):
        """Inicia thread de monitoreo de estudios diferidos."""
        self.defer_monitor_thread = threading.Thread(
            target=self._monitor_deferred_studies,
            name='defer_monitor',
            daemon=True
        )
        self.defer_monitor_thread.start()
        logger.info("✓ Monitor de estudios diferidos iniciado")
    
    def _monitor_queues(self):
        """
        Monitorea tamaños de colas periódicamente.
        Registra alertas si alguna cola supera umbral y stats de rendimiento.
        """
        while not self.shutdown_flag.wait(self.monitor_interval):
            us_size = self.us_queue.qsize()
            bd_size = self.bd_queue.qsize()
            pixel_size = self.pixel_queue.qsize()
            
            total_pending = us_size + bd_size + pixel_size
            
            # Log regular cada ciclo si hay actividad
            if total_pending > 10:
                logger.info(f"📊 Colas pendientes - US: {us_size}, BD: {bd_size}, "
                           f"Pixel: {pixel_size} (Total: {total_pending})")
            
            # Alertas por nivel de saturación
            if us_size > self.degradation_threshold:
                logger.critical(f"🚨 Cola US SATURADA: {us_size}/{self.max_queue_size} - Consider degrading to sync")
            elif us_size > self.alert_threshold:
                logger.warning(f"⚠️  Cola US alta: {us_size}/{self.max_queue_size}")
                
            if bd_size > self.degradation_threshold:
                logger.critical(f"🚨 Cola BD SATURADA: {bd_size}/{self.max_queue_size} - Consider degrading to sync")
            elif bd_size > self.alert_threshold:
                logger.warning(f"⚠️  Cola BD alta: {bd_size}/{self.max_queue_size}")
                
            if pixel_size > self.degradation_threshold:
                logger.critical(f"🚨 Cola Pixel SATURADA: {pixel_size}/{self.max_queue_size}")
            elif pixel_size > self.alert_threshold:
                logger.warning(f"⚠️  Cola Pixel alta: {pixel_size}/{self.max_queue_size}")
            
            # Log de estadísticas de rendimiento cada stats_interval
            current_time = time.time()
            if current_time - self.last_stats_time >= self.stats_interval:
                self._log_performance_stats()
                self.last_stats_time = current_time
    
    def _monitor_deferred_studies(self):
        """
        Monitorea estudios con trabajos diferidos.
        Cuando un estudio no ha recibido instancias por study_completion_timeout segundos,
        considera el estudio completo y dispara el procesamiento de todos sus trabajos.
        """
        logger.info("🔍 Iniciando monitoreo de estudios diferidos...")
        
        while not self.shutdown_flag.wait(self.defer_check_interval):
            current_time = time.time()
            completed_studies = []
            
            with self.active_studies_lock:
                # Identificar estudios que no han recibido instancias recientemente
                for study_uid, study_data in self.active_studies.items():
                    last_activity = study_data['last_activity']
                    inactive_time = current_time - last_activity
                    
                    if inactive_time >= self.study_completion_timeout:
                        completed_studies.append(study_uid)
            
            # Procesar estudios completos
            for study_uid in completed_studies:
                self._process_completed_study(study_uid)
    
    def _process_completed_study(self, study_uid: str):
        """
        Procesa todos los trabajos diferidos de un estudio completo.
        Encola todos los trabajos pendientes y limpia el estudio de active_studies.
        
        Args:
            study_uid: UID del estudio a procesar
        """
        with self.active_studies_lock:
            if study_uid not in self.active_studies:
                return
            
            study_data = self.active_studies.pop(study_uid)
            jobs = study_data.get('jobs', [])
            num_instances = study_data.get('num_instances', 0)
        
        if not jobs:
            logger.debug(f"Estudio {study_uid[:16]}... completo, sin trabajos pendientes")
            return
        
        logger.info(f"✅ Estudio COMPLETO: {study_uid[:16]}... ({num_instances} instancias) - Procesando {len(jobs)} trabajos diferidos")
        
        # Encolar todos los trabajos diferidos
        for job in jobs:
            job_type = job['type']
            job_func = job['func']
            job_args = job['args']
            job_kwargs = job['kwargs']
            
            # Encolar según tipo sin verificar límites (son trabajos legítimos diferidos)
            if job_type == 'us':
                self.submit_us_job(job_func, *job_args, **job_kwargs)
            elif job_type == 'bd':
                self.submit_bd_job(job_func, *job_args, **job_kwargs)
            elif job_type == 'pixel':
                self.submit_pixel_job(job_func, *job_args, **job_kwargs)
        
        logger.info(f"   ✓ {len(jobs)} trabajos encolados para procesamiento")
    
    def defer_study_job(self, study_uid: str, job_type: str, job_func: Callable, *args, **kwargs):
        """
        Difiere un trabajo de procesamiento hasta que el estudio esté completo.
        Actualiza el timestamp de última actividad del estudio.
        
        Args:
            study_uid: UID del estudio
            job_type: Tipo de trabajo ('us', 'bd', 'pixel')
            job_func: Función a ejecutar cuando el estudio esté completo
            args, kwargs: Argumentos para la función
        """
        current_time = time.time()
        
        with self.active_studies_lock:
            if study_uid not in self.active_studies:
                # Nuevo estudio
                self.active_studies[study_uid] = {
                    'last_activity': current_time,
                    'jobs': [],
                    'num_instances': 0,
                }
                logger.debug(f"📋 Nuevo estudio activo: {study_uid[:16]}...")
            
            # Actualizar timestamp y agregar trabajo
            study_data = self.active_studies[study_uid]
            study_data['last_activity'] = current_time
            study_data['num_instances'] += 1
            study_data['jobs'].append({
                'type': job_type,
                'func': job_func,
                'args': args,
                'kwargs': kwargs,
            })
            
            num_jobs = len(study_data['jobs'])
            num_instances = study_data['num_instances']
            
        logger.debug(f"⏳ Trabajo {job_type} DIFERIDO - {study_uid[:16]}... ({num_instances} instancias, {num_jobs} trabajos pendientes)")
    
    def submit_us_job(self, job_func: Callable, *args, **kwargs) -> bool:
        """
        Envía trabajo de reenvío US a la cola.
        
        Args:
            job_func: Función a ejecutar (ej: forward_us_image)
            args, kwargs: Argumentos para la función
            
        Returns:
            bool: True si se encoló exitosamente, False si cola llena o disabled
        """
        if not self.enabled:
            logger.warning("⚠️  Procesamiento asíncrono deshabilitado - omitiendo envío US")
            return False
        
        if self.us_queue.qsize() >= self.max_queue_size:
            logger.critical(f"🚨 Cola US llena ({self.max_queue_size}) - DESCARTANDO trabajo")
            with self.stats_lock:
                self.stats['us_failed'] += 1
            return False
        
        future = self.us_executor.submit(self._wrap_job, 'us', job_func, *args, **kwargs)
        with self.stats_lock:
            self.stats['us_submitted'] += 1
        
        logger.debug(f"✓ Trabajo US encolado (queue size: {self.us_queue.qsize()})")
        return True
    
    def submit_bd_job(self, job_func: Callable, *args, **kwargs) -> bool:
        """
        Envía trabajo de procesamiento BD a la cola.
        
        Args:
            job_func: Función a ejecutar (ej: process_bd_study)
            args, kwargs: Argumentos para la función
            
        Returns:
            bool: True si se encoló exitosamente, False si cola llena o disabled
        """
        if not self.enabled:
            logger.warning("⚠️  Procesamiento asíncrono deshabilitado - omitiendo envío BD")
            return False
        
        if self.bd_queue.qsize() >= self.max_queue_size:
            logger.critical(f"🚨 Cola BD llena ({self.max_queue_size}) - DESCARTANDO trabajo")
            with self.stats_lock:
                self.stats['bd_failed'] += 1
            return False
        
        future = self.bd_executor.submit(self._wrap_job, 'bd', job_func, *args, **kwargs)
        with self.stats_lock:
            self.stats['bd_submitted'] += 1
        
        logger.debug(f"✓ Trabajo BD encolado (queue size: {self.bd_queue.qsize()})")
        return True
    
    def submit_pixel_job(self, job_func: Callable, *args, **kwargs) -> bool:
        """
        Envía trabajo de extracción de píxeles a la cola.
        
        Args:
            job_func: Función a ejecutar (ej: extract_and_save_pixel_map)
            args, kwargs: Argumentos para la función
            
        Returns:
            bool: True si se encoló exitosamente, False si cola llena or disabled
        """
        if not self.enabled:
            logger.warning("⚠️  Procesamiento asíncrono deshabilitado - omitiendo extracción pixel")
            return False
        
        if self.pixel_queue.qsize() >= self.max_queue_size:
            logger.critical(f"🚨 Cola Pixel llena ({self.max_queue_size}) - DESCARTANDO trabajo")
            with self.stats_lock:
                self.stats['pixel_failed'] += 1
            return False
        
        future = self.pixel_executor.submit(self._wrap_job, 'pixel', job_func, *args, **kwargs)
        with self.stats_lock:
            self.stats['pixel_submitted'] += 1
        
        logger.debug(f"✓ Trabajo Pixel encolado (queue size: {self.pixel_queue.qsize()})")
        return True
    
    def _wrap_job(self, job_type: str, job_func: Callable, *args, **kwargs):
        """
        Wrapper que ejecuta un trabajo y actualiza estadísticas.
        
        Args:
            job_type: Tipo de trabajo ('us', 'bd', 'pixel')
            job_func: Función a ejecutar
            args, kwargs: Argumentos para la función
        """
        try:
            start_time = time.time()
            result = job_func(*args, **kwargs)
            duration_ms = int((time.time() - start_time) * 1000)
            
            with self.stats_lock:
                self.stats[f'{job_type}_completed'] += 1
            
            logger.debug(f"✓ Trabajo {job_type} completado en {duration_ms}ms")
            return result
            
        except Exception as e:
            with self.stats_lock:
                self.stats[f'{job_type}_failed'] += 1
            
            logger.error(f"❌ Error en trabajo {job_type}: {e}", exc_info=True)
            raise
    
    def get_stats(self) -> Dict[str, int]:
        """
        Retorna estadísticas actuales de procesamiento.
        
        Returns:
            Dict con contadores de trabajos submitted/completed/failed
        """
        with self.stats_lock:
            return self.stats.copy()
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """
        Retorna tamaños actuales de las colas.
        
        Returns:
            Dict con tamaños de cada cola
        """
        return {
            'us_queue': self.us_queue.qsize(),
            'bd_queue': self.bd_queue.qsize(),
            'pixel_queue': self.pixel_queue.qsize(),
        }
    
    def is_saturated(self) -> bool:
        """
        Verifica si alguna cola está saturada (cerca del límite).
        
        Returns:
            True si alguna cola supera degradation_threshold
        """
        if not self.enabled:
            return False
            
        us_size = self.us_queue.qsize()
        bd_size = self.bd_queue.qsize()
        pixel_size = self.pixel_queue.qsize()
        
        return (us_size > self.degradation_threshold or 
                bd_size > self.degradation_threshold or
                pixel_size > self.degradation_threshold)
    
    def _log_performance_stats(self):
        """
        Registra estadísticas detalladas de rendimiento.
        """
        with self.stats_lock:
            stats = self.stats.copy()
        
        # Calcular tasas de éxito
        us_total = stats['us_submitted']
        us_success_rate = (stats['us_completed'] / us_total * 100) if us_total > 0 else 0
        
        bd_total = stats['bd_submitted']
        bd_success_rate = (stats['bd_completed'] / bd_total * 100) if bd_total > 0 else 0
        
        pixel_total = stats['pixel_submitted']
        pixel_success_rate = (stats['pixel_completed'] / pixel_total * 100) if pixel_total > 0 else 0
        
        # Log estadísticas
        logger.info(f"📈 ASYNC STATS - US: {stats['us_submitted']}S / {stats['us_completed']}C / "
                   f"{stats['us_failed']}F ({us_success_rate:.1f}%)")
        logger.info(f"📈 ASYNC STATS - BD: {bd_total}S / {stats['bd_completed']}C / "
                   f"{stats['bd_failed']}F ({bd_success_rate:.1f}%)")
        logger.info(f"📈 ASYNC STATS - Pixel: {pixel_total}S / {stats['pixel_completed']}C / "
                   f"{stats['pixel_failed']}F ({pixel_success_rate:.1f}%)")
        
        # Queue depths
        sizes = self.get_queue_sizes()
        logger.info(f"📊 QUEUE DEPTHS - US: {sizes['us_queue']}, BD: {sizes['bd_queue']}, "
                   f"Pixel: {sizes['pixel_queue']}")
    
    def get_queue_sizes(self) -> Dict[str, int]:
        """
        Retorna tamaños actuales de colas.
        
        Returns:
            Dict con tamaños de cada cola
        """
        return {
            'us_queue': self.us_queue.qsize(),
            'bd_queue': self.bd_queue.qsize(),
            'pixel_queue': self.pixel_queue.qsize(),
        }
    
    def shutdown(self, timeout: int = 30):
        """
        Apagado graceful - espera a que workers finalicen trabajos en vuelo.
        
        Args:
            timeout: Segundos máximos a esperar por finalización de workers
        """
        if not self.enabled:
            return
        
        logger.info("🛑 Iniciando shutdown graceful de QueueManager...")
        
        # Detener monitor
        self.shutdown_flag.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        # Shutdown de executors (espera a trabajos en vuelo)
        for name, executor in [('US', self.us_executor), 
                              ('BD', self.bd_executor), 
                              ('Pixel', self.pixel_executor)]:
            if executor:
                logger.info(f"⏳ Esperando finalización de workers {name}...")
                executor.shutdown(wait=True, cancel_futures=False)
                logger.info(f"✓ Workers {name} finalizados")
        
        # Log de estadísticas finales
        stats = self.get_stats()
        logger.info(f"📊 Estadísticas finales:")
        logger.info(f"   US - enviados: {stats['us_submitted']}, "
                   f"completados: {stats['us_completed']}, "
                   f"fallados: {stats['us_failed']}")
        logger.info(f"   BD - enviados: {stats['bd_submitted']}, "
                   f"completados: {stats['bd_completed']}, "
                   f"fallados: {stats['bd_failed']}")
        logger.info(f"   Pixel - enviados: {stats['pixel_submitted']}, "
                   f"completados: {stats['pixel_completed']}, "
                   f"fallados: {stats['pixel_failed']}")
        
        logger.info("✓ QueueManager apagado exitosamente")


# Instancia global (será inicializada en main.py)
_queue_manager: Optional[QueueManager] = None


def initialize_queue_manager(config: Dict[str, Any]) -> QueueManager:
    """
    Inicializa la instancia global del QueueManager.
    
    Args:
        config: Diccionario con configuración ASYNC_PROCESSING
        
    Returns:
        Instancia de QueueManager
    """
    global _queue_manager
    _queue_manager = QueueManager(config)
    return _queue_manager


def get_queue_manager() -> Optional[QueueManager]:
    """
    Obtiene la instancia global del QueueManager.
    
    Returns:
        Instancia de QueueManager o None si no está inicializada
    """
    return _queue_manager
