# DICOM Receiver Service - YouTube Video Script

**Video Title:** Building a DICOM Receiver Service for Medical Image AI Processing

**Target Audience:** Healthcare IT professionals, Medical Imaging specialists, AI/ML engineers, PACS administrators

**Video Duration:** ~15-20 minutes

**Language:** English

---

## 📺 VIDEO SCRIPT

### [INTRO - 0:00-0:30]

**[VISUAL: Title animation with medical imaging background]**

**Narrator:**
"Managing medical imaging data can be complex. Whether you're building AI solutions, analyzing patient images, or integrating multiple PACS systems, you need a reliable way to receive DICOM images from one system and prepare them for advanced processing.

Today, I'm showing you a complete solution: the DICOM Receiver Service - an open-source tool that makes it simple to receive medical images via the DICOM protocol and prepare them for AI-powered post-processing."

---

### [SECTION 1: THE PROBLEM - 0:30-2:00]

**[VISUAL: Show a typical PACS system interface, then show frustration/complexity]**

**Narrator:**
"Here's a common scenario: You have a PACS system - your primary Picture Archiving and Communication System - that stores thousands of medical images. You want to:

- Export images from your existing PACS
- Run custom AI algorithms for image enhancement or diagnosis
- Process images in batch operations
- Integrate with a machine learning pipeline
- Store processed results back to your system

[VISUAL: Show multiple incompatible systems trying to communicate]

But connecting systems is hard. Different PACS vendors, different protocols, incompatible formats... it's frustrating.

[VISUAL: Highlight the solution]

That's where the DICOM Receiver Service comes in. It acts as a bridge between your PACS and your AI processing pipeline."

---

### [SECTION 2: THE SOLUTION - 2:00-3:30]

**[VISUAL: Clean diagram showing PACS → DICOM Receiver → AI Processing → Results]**

**Narrator:**
"The DICOM Receiver Service is a lightweight, purpose-built application that:

✓ Listens for DICOM images exported from your PACS using the C-STORE protocol
✓ Receives and validates incoming medical images
✓ Organizes them in a structured directory hierarchy
✓ Prepares them for post-processing with AI algorithms
✓ Runs continuously on your server with automatic restart capabilities
✓ Provides detailed logging for monitoring and troubleshooting

[VISUAL: Show the service architecture diagram]

It's built with Python, using industry-standard libraries for DICOM handling - pydicom and pynetdicom. It's designed to be:

- **Reliable:** Runs as a systemd service with automatic restart on failure
- **Easy to integrate:** Standard DICOM protocol - compatible with any PACS
- **Production-ready:** Complete with logging, error handling, and configuration options
- **Open source:** Fully customizable for your specific needs"

---

### [SECTION 3: KEY FEATURES - 3:30-5:00]

**[VISUAL: Feature list with icons/animations]**

**Narrator:**
"Let me break down the key features:

**1. DICOM C-STORE Protocol Support**

[VISUAL: Show C-STORE protocol diagram]

The service listens on port 5665 and receives DICOM images using the standard C-STORE protocol. This means any PACS system that supports DICOM can send images to it.

**2. Automatic File Organization**

[VISUAL: Show directory structure expanding]

When images arrive, they're automatically organized by:
- Patient ID
- Study Instance UID
- Modality type
- Timestamp
- SOP Instance UID

This creates a logical structure that's easy for AI algorithms to process.

**3. Multiple Modality Support**

[VISUAL: Show list of supported modalities]

The service supports 7 different medical imaging modalities:
- CT (Computed Tomography)
- MR (Magnetic Resonance)
- US (Ultrasound)
- XRA (X-Ray Angiography)
- CR (Computed Radiography)
- DX (Digital X-Ray)
- MG (Mammography)

**4. Systemd Integration**

[VISUAL: Show systemctl commands]

It runs as a proper Linux service, which means:
- Automatic startup on server reboot
- One-command restart if anything fails
- Integration with system logging
- Professional service management"

---

### [SECTION 4: INSTALLATION WALKTHROUGH - 5:00-10:00]

**[VISUAL: Terminal screen, step-by-step installation]**

**Narrator:**
"Let's install and configure the service. I'll walk you through each step.

**STEP 1: Prerequisites**

[VISUAL: Show system requirements list]

You need:
- Ubuntu/Debian Linux system (any recent version)
- Python 3.8 or higher
- Sudo access (for installing the service)
- A few MB of disk space

**STEP 2: Download the Project**

[VISUAL: Terminal showing git clone command]

```
git clone <repository-url>
cd DICOMReceiver
```

Or if you're on my GitHub, you can download the zip file directly.

**STEP 3: Install Dependencies**

[VISUAL: Terminal showing pip install]

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

This creates a Python virtual environment and installs the two libraries you need:
- pydicom: For reading and writing DICOM files
- pynetdicom: For the DICOM network protocol

This takes about 2-3 minutes depending on your internet connection.

**STEP 4: Create Storage Directory**

[VISUAL: Terminal showing mkdir command]

```
mkdir -p dicom_storage
```

This is where your DICOM images will be saved. The service will automatically organize them.

**STEP 5: Install as a Service**

[VISUAL: Terminal showing service installation]

This is where it gets powerful. Run:

```
sudo bash install-service.sh
```

This script:
- Creates the systemd service file
- Configures it to run on startup
- Enables automatic restart on failure
- Sets up proper logging

**STEP 6: Start the Service**

[VISUAL: Terminal showing systemctl start command]

```
sudo systemctl start dicom-receiver
```

Your DICOM Receiver is now running!

**STEP 7: Verify It's Working**

[VISUAL: Terminal showing status check]

```
sudo systemctl status dicom-receiver
```

You should see:
- Active: active (running)
- Listening on port 5665
- Memory usage around 25MB

[VISUAL: Show successful output]

That's it! The service is installed and running. The entire process takes about 5 minutes."

---

### [SECTION 5: CONFIGURATION & CUSTOMIZATION - 10:00-11:30]

**[VISUAL: Text editor showing config.py]**

**Narrator:**
"The service is highly customizable. Open the config.py file:

**Change the Port**

[VISUAL: Highlight port configuration]

By default, it listens on port 5665. If you need a different port, edit config.py:

```python
DICOM_SERVER = {
    'port': 5665,  # Change this number
    ...
}
```

**Change Storage Location**

[VISUAL: Highlight storage path]

By default, images are stored in ./dicom_storage. You can change this:

```python
STORAGE = {
    'base_path': './dicom_storage',  # Change to any path
    ...
}
```

**Adjust Logging Level**

[VISUAL: Show logging configuration]

You can control how much detail is logged:

```python
LOGGING = {
    'level': 'INFO',  # Can be DEBUG, INFO, WARNING, ERROR
    ...
}
```

After making changes, simply restart:

```
sudo systemctl restart dicom-receiver
```

No complicated recompilation. Just edit, save, and restart."

---

### [SECTION 6: USING THE SERVICE - 11:30-15:00]

**[VISUAL: Show PACS system sending images, then show received images]**

**Narrator:**
"Now let's see how to actually use this service in your workflow.

**STEP 1: Configure Your PACS**

[VISUAL: Show PACS configuration screen]

In your PACS system, you need to set up a DICOM export destination:

- **Server:** The IP address or hostname of your Linux server
- **Port:** 5665 (or your custom port)
- **AET:** DICOM_RECEIVER (the service identifier)
- **Protocol:** C-STORE

Every PACS is different, but they all have a section for 'Send Images' or 'Export Destination'. You add your DICOM Receiver as a destination.

**STEP 2: Export Images from Your PACS**

[VISUAL: Show PACS export dialog]

In your PACS:
1. Select one or more images
2. Choose 'Send' or 'Export'
3. Select 'DICOM_RECEIVER' as the destination
4. Click 'Send'

The images travel from your PACS to the DICOM Receiver service over the network using the standard DICOM protocol.

**STEP 3: Monitor Reception**

[VISUAL: Terminal showing log output]

To see the images being received in real-time:

```
sudo journalctl -u dicom-receiver -f
```

You'll see output like:

```
Patient: P001, Study: 1.2.3.4, File: CT_20251224_143022_1.2.3.4.5.dcm
Patient: P002, Study: 1.2.3.5, File: MR_20251224_143045_1.2.3.4.6.dcm
```

Each line shows:
- Which patient the image belongs to
- The study identifier
- The filename where it was saved

**STEP 4: Access the Files for Processing**

[VISUAL: Show directory structure]

Your received images are stored organized by patient and study:

```
dicom_storage/
├── P001/
│   └── 1.2.3.4/
│       ├── CT_20251224_143022_1.2.3.4.5.dcm
│       └── CT_20251224_143045_1.2.3.4.6.dcm
└── P002/
    └── 1.2.3.5/
        └── MR_20251224_143050_1.2.3.4.7.dcm
```

This makes it very easy for your AI algorithms to:
- Find all images for a specific patient
- Find all images from a specific study
- Process them in batch operations

**STEP 5: Process with AI**

[VISUAL: Show Python script reading DICOM files]

Your AI pipeline can now read these files. For example, with pydicom:

```python
import pydicom
from pathlib import Path

# Find all CT images
ct_images = Path('dicom_storage').glob('*/*/*.dcm')

for image_path in ct_images:
    # Load DICOM file
    ds = pydicom.dcmread(image_path)
    
    # Your AI algorithm here
    processed_image = your_ai_model.process(ds.pixel_array)
    
    # Save results
    ds.pixel_array = processed_image
    ds.save_as(f'{image_path.parent}/processed_{image_path.name}')
```

The structured organization makes this very straightforward.

**STEP 6: Service Management**

[VISUAL: Show command reference]

Once the service is running, you can manage it with simple commands:

Start the service:
```
sudo systemctl start dicom-receiver
```

Stop the service:
```
sudo systemctl stop dicom-receiver
```

Restart the service:
```
sudo systemctl restart dicom-receiver
```

Check status:
```
sudo systemctl status dicom-receiver
```

Enable on startup (it's already enabled):
```
sudo systemctl enable dicom-receiver
```

View logs from the last 100 entries:
```
sudo journalctl -u dicom-receiver -n 100
```

These are standard Linux service commands, so if you're familiar with systemd, you already know how to manage this."

---

### [SECTION 7: REAL-WORLD EXAMPLE - 15:00-17:30]

**[VISUAL: Show complete workflow diagram]**

**Narrator:**
"Let me show you a real-world example of how this works in a medical imaging AI project.

**Scenario:** A hospital wants to implement AI-assisted diagnosis for chest X-rays.

**The Workflow:**

1. **Radiologist exports chest X-rays from the main PACS**
   [VISUAL: Show PACS with X-ray images]
   They select 100 recent X-rays and send them to the DICOM Receiver.

2. **Images arrive and are organized**
   [VISUAL: Show directory structure being populated]
   The service receives them on port 5665 and organizes them by patient and study.

3. **AI processing pipeline starts**
   [VISUAL: Show Python script processing]
   An automated script reads the organized files and runs them through an AI model trained to detect pneumonia, nodules, etc.

4. **Results are generated**
   [VISUAL: Show heatmaps and annotations]
   The AI model outputs:
   - Probability scores for abnormalities
   - Heatmaps showing areas of concern
   - Structured reports

5. **Results are imported back to PACS**
   [VISUAL: Show results in PACS system]
   The radiologist reviews the AI-assisted analysis alongside the original images.

The entire process from export to AI analysis to results takes minutes instead of hours. And it's all automated.

**Why This Matters:**

- **Speed:** Radiologists get AI-assisted analysis faster
- **Consistency:** Algorithms are applied uniformly to all images
- **Workflow integration:** Works with existing PACS systems
- **Scalability:** Can process hundreds of images per day
- **Auditability:** Complete logs of what was processed and when"

---

### [SECTION 8: TROUBLESHOOTING & SUPPORT - 17:30-19:00]

**[VISUAL: Show common error scenarios and solutions]**

**Narrator:**
"Let's talk about what to do if something goes wrong.

**Problem 1: Service won't start**

[VISUAL: Show error output]

Check the logs:
```
sudo journalctl -u dicom-receiver -n 20
```

This will show you the last 20 log entries and usually reveals the problem.

**Problem 2: Port already in use**

[VISUAL: Show port conflict]

If port 5665 is already in use:

```
sudo lsof -i :5665
```

This shows what's using the port. Either:
- Stop the other service
- Change the port in config.py

**Problem 3: Permission errors**

[VISUAL: Show permission denied error]

Make sure the storage directory is writable:

```
ls -la dicom_storage/
```

If needed, fix permissions:

```
chmod 755 dicom_storage/
```

**Problem 4: Images not being received**

[VISUAL: Show PACS configuration check]

Verify:
- Correct IP address or hostname
- Correct port number (5665)
- Correct AET (DICOM_RECEIVER)
- Service is running: `sudo systemctl status dicom-receiver`

**Problem 5: Need to uninstall**

[VISUAL: Show uninstall steps]

To completely remove the service:

```
sudo systemctl stop dicom-receiver
sudo systemctl disable dicom-receiver
sudo rm /etc/systemd/system/dicom-receiver.service
sudo systemctl daemon-reload
```

The code and files remain in your DICOMReceiver folder for future use.

**Getting Help:**

- Check the comprehensive documentation in README.md
- See the detailed service guide in SERVICE.md
- Review the installation notes in INSTALLATION_COMPLETED.md
- All files have detailed comments explaining the code"

---

### [SECTION 9: ADVANCED TOPICS - 19:00-20:30]

**[VISUAL: Show advanced configuration options]**

**Narrator:**
"For advanced users, here are some topics you might want to explore:

**1. Multiple Instances**

You can run multiple instances of the service on different ports:
- Production PACS → Port 5665
- Test PACS → Port 5666
- Development → Port 5667

Just copy the service file and change the port. Each instance runs independently.

**2. Integration with AI Frameworks**

The service pairs well with:
- TensorFlow for medical imaging models
- PyTorch for deep learning
- OpenCV for image processing
- scikit-learn for traditional ML

Since images are saved as standard DICOM files, you use any library you want.

**3. Batch Processing**

Create a Python script that:
- Watches the dicom_storage directory
- When new images arrive, automatically processes them
- Stores results in a separate directory
- Notifies you when complete

**4. Integration with PACS**

Some advanced setups:
- Send AI results back to original PACS
- Create DICOM reports automatically
- Build a complete AI-assisted workflow

**5. Performance Optimization**

For high-volume scenarios:
- Add SSD storage for faster image access
- Configure multiple concurrent connections
- Use a load balancer if deploying multiple servers
- Monitor with Prometheus/Grafana

**6. Security Hardening**

For production deployments:
- Add TLS encryption (DICOM-over-TLS)
- Implement AET validation
- Use firewall rules to restrict access
- Enable audit logging
- Regular security updates

These topics are beyond the scope of this video, but they're all supported by the architecture."

---

### [SECTION 10: CONCLUSION & CALL TO ACTION - 20:30-21:00]

**[VISUAL: Show project repository, GitHub links]**

**Narrator:**
"The DICOM Receiver Service is a complete, production-ready solution for receiving medical images from your PACS and preparing them for AI processing.

It's:
- Free and open source
- Easy to install (5 minutes)
- Simple to configure
- Reliable and well-documented
- Perfect for medical imaging AI projects

**What you can do next:**

1. **Download the project** from the GitHub repository (link in the description)
2. **Follow the installation guide** in the README.md file
3. **Set it up on your server** - it'll take you about 30 minutes
4. **Configure your PACS** to send images to the service
5. **Start building AI** medical imaging solutions

**If you found this helpful:**
- Please like and subscribe for more healthcare IT content
- Let me know in the comments if you have questions
- Share this video with colleagues who might benefit

**Resources mentioned:**
- GitHub repository: [link]
- Documentation: README.md, SERVICE.md
- Configuration guide: config.py
- Test script: test.py

Thanks for watching, and happy imaging!"

---

## 📝 VIDEO PRODUCTION NOTES

### B-Roll Suggestions

**0:00-0:30 (Intro)**
- Medical imaging backgrounds
- PACS system interface footage
- Server/cloud imagery

**0:30-2:00 (Problem)**
- Multiple PACS systems
- Data flow diagrams
- Frustrated professionals working
- Incompatible systems icons

**2:00-3:30 (Solution)**
- Clean architecture diagram
- DICOM Receiver interface
- AI processing visualization
- Server running animation

**3:30-5:00 (Features)**
- Protocol diagrams
- Directory tree expanding
- Medical imaging modalities (CT, MR, etc.)
- Linux terminal with systemctl commands

**5:00-10:00 (Installation)**
- Terminal windows with commands
- Code snippets highlighting
- Progress bars/animations
- Successful installation confirmation

**10:00-11:30 (Configuration)**
- Text editor showing config.py
- Highlighting key configuration parameters
- Before/after comparisons

**11:30-15:00 (Usage)**
- PACS system export dialogs
- Real DICOM images (with privacy - no patient data visible)
- Log output scrolling
- Directory structure animation

**15:00-17:30 (Real-world example)**
- Hospital workflow diagram
- Medical imaging AI visualization
- Results with heatmaps (no patient identifiable info)
- Before/after images

**17:30-19:00 (Troubleshooting)**
- Terminal error messages
- Solutions with command demonstrations
- Success confirmations

**19:00-20:30 (Advanced)**
- Architecture diagrams
- Code snippets
- Performance graphs
- Deployment scenarios

**20:30-21:00 (Conclusion)**
- GitHub repository screenshot
- Project files listing
- Call-to-action graphics
- Subscription prompt

### Audio Suggestions

- Professional background music (royalty-free, medical tech themed)
- Use a clear, professional narrator voice
- Add subtle sound effects for transitions
- Emphasis on key technical terms
- Slower pacing for technical sections

### Text Overlays

- Key points highlighted during narration
- Command examples in readable font
- Configuration snippets with syntax highlighting
- Statistics and metrics
- Section titles with timestamps

### Pacing Guide

- **0:00-5:00:** Slower pace, establish problem and solution
- **5:00-10:00:** Medium pace, step-by-step installation
- **10:00-15:00:** Medium pace, practical usage
- **15:00-20:30:** Varied pace, examples and advanced topics
- **20:30-21:00:** Quick pace, call to action

---

## 📊 SEO & METADATA

**Title:** Building a DICOM Receiver Service for Medical Image AI Processing | C-STORE Protocol Tutorial

**Description:**
Learn how to build and deploy a DICOM Receiver Service for medical imaging AI applications. This complete guide covers:
- What is DICOM and C-STORE protocol
- Installation and setup (step-by-step)
- Configuration and customization
- Real-world AI integration examples
- Troubleshooting and best practices

Perfect for radiologists, healthcare IT professionals, medical imaging engineers, and AI developers.

🔗 GitHub Repository: [link]
📚 Documentation: See repo for complete guides
⏱️ Timestamps: [include chapter markers]

**Keywords:**
DICOM, PACS, medical imaging, AI, machine learning, C-STORE, healthcare IT, image processing, Python, Linux service, healthcare technology, radiography, diagnosis AI, image analysis, medical data

**Tags:**
#DICOM #PACS #MedicalImaging #HealthcareIT #AI #MachineLearning #Python #Linux #OpenSource #ImageProcessing #Radiology #HealthTech #Tutorial #DevOps

---

## ✅ PRODUCTION CHECKLIST

- [ ] Record intro with title animation
- [ ] Record section 1 (problem) with B-roll
- [ ] Record section 2 (solution) with architecture diagram
- [ ] Record section 3 (features) with visual highlights
- [ ] Record section 4 (installation) with live terminal
- [ ] Record section 5 (configuration) with code editor
- [ ] Record section 6 (usage) with PACS simulation
- [ ] Record section 7 (real-world) with workflow diagram
- [ ] Record section 8 (troubleshooting) with examples
- [ ] Record section 9 (advanced) with diagrams
- [ ] Record section 10 (conclusion) with call-to-action
- [ ] Add background music
- [ ] Add text overlays and titles
- [ ] Color grade for consistency
- [ ] Review audio quality
- [ ] Add captions/subtitles
- [ ] Add chapter markers
- [ ] Test on different platforms
- [ ] Final quality check
- [ ] Optimize for YouTube recommendations
- [ ] Create thumbnail
- [ ] Schedule upload
- [ ] Share on social media

---

**Script Version:** 1.0  
**Last Updated:** December 24, 2025  
**Language:** English  
**Estimated Length:** 20 minutes  
**Difficulty Level:** Intermediate (suitable for tech-savvy healthcare professionals)
