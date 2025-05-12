from flask import Flask, request, render_template, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pydub import AudioSegment
from pydub.utils import mediainfo
import os
import uuid
import time
import threading
import logging
import hashlib
import json
import fcntl
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # Limit uploads to 100MB
app.config['UPLOAD_FOLDER'] = 'temp_uploads'
app.config['CONVERTED_FOLDER'] = 'temp_converted'
app.config['TASKS_FILE'] = 'conversion_tasks.json'
app.config['FILE_RETENTION_MINUTES'] = 30

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure our temporary directories exist with proper permissions
for folder in [app.config['UPLOAD_FOLDER'], app.config['CONVERTED_FOLDER']]:
    os.makedirs(folder, exist_ok=True)
    try:
        # Try to make sure the directory is writable
        os.chmod(folder, 0o777)  # Full permissions - be careful in production!
        logger.info(f"Set permissions on {folder}")
    except Exception as e:
        logger.warning(f"Couldn't set permissions on {folder}: {e}")

# Initialize tasks file if it doesn't exist
if not os.path.exists(app.config['TASKS_FILE']):
    try:
        with open(app.config['TASKS_FILE'], 'w') as f:
            json.dump({}, f)
        os.chmod(app.config['TASKS_FILE'], 0o666)  # Make writable by all users
        logger.info(f"Created tasks file: {app.config['TASKS_FILE']}")
    except Exception as e:
        logger.error(f"Failed to create tasks file: {e}")

def get_tasks():
    """Get all tasks from the tasks file with file locking to prevent race conditions"""
    try:
        with open(app.config['TASKS_FILE'], 'r') as f:
            fcntl.flock(f, fcntl.LOCK_SH)  # Shared lock for reading
            try:
                tasks = json.load(f)
            except json.JSONDecodeError:
                logger.error("Invalid JSON in tasks file, resetting")
                tasks = {}
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
        return tasks
    except Exception as e:
        logger.error(f"Error reading tasks: {e}")
        return {}

def save_task(task_id, task_data):
    """Save a task to the tasks file with file locking"""
    try:
        tasks = get_tasks()
        tasks[task_id] = task_data
        
        with open(app.config['TASKS_FILE'], 'w') as f:
            fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
            try:
                json.dump(tasks, f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
        
        return True
    except Exception as e:
        logger.error(f"Error saving task {task_id}: {e}")
        return False

def delete_task(task_id):
    """Delete a task from the tasks file"""
    try:
        tasks = get_tasks()
        if task_id in tasks:
            del tasks[task_id]
            
            with open(app.config['TASKS_FILE'], 'w') as f:
                fcntl.flock(f, fcntl.LOCK_EX)  # Exclusive lock for writing
                try:
                    json.dump(tasks, f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)  # Release lock
        
        return True
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        return False

def get_file_md5(filepath):
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def cleanup_old_files():
    """Remove files older than the retention period"""
    while True:
        try:
            now = datetime.now()
            retention_delta = timedelta(minutes=app.config['FILE_RETENTION_MINUTES'])
            
            # Check both directories
            for folder in [app.config['UPLOAD_FOLDER'], app.config['CONVERTED_FOLDER']]:
                for filename in os.listdir(folder):
                    file_path = os.path.join(folder, filename)
                    file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    if now - file_modified > retention_delta:
                        try:
                            os.remove(file_path)
                            logger.info(f"Cleaned up old file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove {file_path}: {e}")
            
            # Also clean up old tasks
            tasks = get_tasks()
            current_time = time.time()
            tasks_to_delete = []
            
            for task_id, task_data in tasks.items():
                # Check if task is older than retention period
                if 'timestamp' in task_data:
                    task_age = current_time - task_data['timestamp']
                    if task_age > (app.config['FILE_RETENTION_MINUTES'] * 60):
                        tasks_to_delete.append(task_id)
            
            # Delete old tasks
            for task_id in tasks_to_delete:
                delete_task(task_id)
                logger.info(f"Cleaned up old task: {task_id}")
                
        except Exception as e:
            logger.error(f"Error in cleanup thread: {e}")
            
        # Run every 5 minutes
        time.sleep(300)

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

def convert_audio(input_path, output_dir, task_id):
    """Convert audio to mono 8kHz 16-bit WAV with verification"""
    try:
        # Update task status to processing
        save_task(task_id, {
            'status': 'processing',
            'progress': 0,
            'timestamp': time.time()
        })
        
        # Generate output path
        original_filename = os.path.basename(input_path)
        base_name = os.path.splitext(original_filename)[0]
        output_filename = f"{base_name}_mono_8khz_16bit.wav"
        sanitized_output_filename = secure_filename(output_filename)
        output_path = os.path.join(output_dir, f"{task_id}_{sanitized_output_filename}")
        
        # First verify the input file is actually an audio file
        save_task(task_id, {
            'status': 'processing',
            'progress': 5,
            'timestamp': time.time()
        })
        
        try:
            # Just try to get file info without loading whole file
            info = mediainfo(input_path)
            if not info or 'sample_rate' not in info:
                raise Exception("Input file does not appear to be a valid audio file")
            
            logger.info(f"Input file format: {info.get('format_name', 'unknown')}")
            logger.info(f"Input sample rate: {info.get('sample_rate', 'unknown')}")
            logger.info(f"Input bit depth: {info.get('bit_depth', 'unknown')}")
            logger.info(f"Input channels: {info.get('channels', 'unknown')}")
        except Exception as e:
            logger.error(f"Input validation failed: {e}")
            save_task(task_id, {
                'status': 'error',
                'error': "Invalid audio file format",
                'timestamp': time.time()
            })
            return None
        
        # Load the audio file - this may take time for large files
        save_task(task_id, {
            'status': 'processing',
            'progress': 10,
            'timestamp': time.time()
        })
        
        sound = AudioSegment.from_file(input_path)
        
        # Store original properties for verification
        original_channels = sound.channels
        original_frame_rate = sound.frame_rate
        original_sample_width = sound.sample_width
        
        # Update progress
        save_task(task_id, {
            'status': 'processing',
            'progress': 30,
            'timestamp': time.time()
        })
        
        # Make mono if not already
        if sound.channels > 1:
            sound = sound.set_channels(1)
        
        save_task(task_id, {
            'status': 'processing',
            'progress': 50,
            'timestamp': time.time()
        })
        
        # Set sample rate if not already 8kHz
        if sound.frame_rate != 8000:
            sound = sound.set_frame_rate(8000)
            
        save_task(task_id, {
            'status': 'processing',
            'progress': 70,
            'timestamp': time.time()
        })
        
        # Set sample width if not already 16-bit
        if sound.sample_width != 2:  # 2 bytes = 16-bit
            sound = sound.set_sample_width(2)
            
        save_task(task_id, {
            'status': 'processing',
            'progress': 85,
            'timestamp': time.time()
        })
        
        # Export as WAV using explicit parameters to ensure proper WAV encoding
        sound.export(output_path, format="wav", 
                    parameters=["-acodec", "pcm_s16le", "-ac", "1", "-ar", "8000"])
        
        # Verify the conversion
        save_task(task_id, {
            'status': 'processing',
            'progress': 95,
            'timestamp': time.time()
        })
        
        if os.path.exists(output_path):
            # Calculate input and output file sizes
            input_size = os.path.getsize(input_path)
            output_size = os.path.getsize(output_path)
            
            # Validate output file
            try:
                converted_sound = AudioSegment.from_file(output_path)
                
                # Verify properties
                if converted_sound.channels != 1 or abs(converted_sound.frame_rate - 8000) > 10 or converted_sound.sample_width != 2:
                    logger.error(f"Conversion validation failed - wrong properties: channels={converted_sound.channels}, rate={converted_sound.frame_rate}, width={converted_sound.sample_width}")
                    raise Exception("Converted file has incorrect audio properties")
                    
                # Log size differences for debugging
                logger.info(f"Original size: {input_size} bytes, Converted size: {output_size} bytes")
                logger.info(f"Original: channels={original_channels}, rate={original_frame_rate}, width={original_sample_width}")
                logger.info(f"Converted: channels=1, rate=8000, width=2")
                
                # Calculate and log MD5 hashes for comparison
                input_md5 = get_file_md5(input_path)
                output_md5 = get_file_md5(output_path)
                logger.info(f"Input MD5: {input_md5}")
                logger.info(f"Output MD5: {output_md5}")
                
                # If input and output are identical, that's a problem
                if input_md5 == output_md5:
                    logger.error("Input and output files have identical MD5 hashes - conversion failed")
                    raise Exception("Conversion did not change the audio file")
                
                # If MP3 and WAV are very close in size and conversion appears to have no effect,
                # it might indicate a problem (unless the source was already mono/8kHz/16-bit)
                if abs(input_size - output_size) < (input_size * 0.05):
                    if original_channels == 1 and abs(original_frame_rate - 8000) < 10 and original_sample_width == 2:
                        logger.info("Input was already in target format, minimal changes expected")
                    else:
                        logger.warning("Suspicious: input and output files are very similar in size but should be different")
                        # We'll continue but log this warning
                
            except Exception as e:
                logger.error(f"Output validation failed: {e}")
                save_task(task_id, {
                    'status': 'error',
                    'error': f"Conversion validation failed: {str(e)}",
                    'timestamp': time.time()
                })
                return None
        else:
            logger.error("Output file was not created")
            save_task(task_id, {
                'status': 'error',
                'error': "Conversion failed - no output file",
                'timestamp': time.time()
            })
            return None
            
        # Successful conversion - update status
        save_task(task_id, {
            'status': 'complete',
            'progress': 100,
            'output_path': output_path,
            'filename': sanitized_output_filename,
            'original_size': input_size,
            'converted_size': output_size,
            'original_format': {
                'channels': original_channels,
                'sample_rate': original_frame_rate,
                'bit_depth': original_sample_width * 8
            },
            'timestamp': time.time()
        })
        
        return output_path
        
    except Exception as e:
        logger.error(f"Error converting {input_path}: {e}")
        save_task(task_id, {
            'status': 'error',
            'error': str(e),
            'timestamp': time.time()
        })
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'audiofile' not in request.files:
        return jsonify({'error': 'No file part'}), 400
        
    file = request.files['audiofile']
    
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    if file:
        try:
            # Generate a unique ID for this conversion task
            task_id = str(uuid.uuid4())
            
            # Save uploaded file
            filename = secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{task_id}_{filename}")
            
            # Test directory permissions before saving
            if not os.access(app.config['UPLOAD_FOLDER'], os.W_OK):
                logger.error(f"Upload directory {app.config['UPLOAD_FOLDER']} is not writable")
                return jsonify({'error': 'Server configuration error: upload directory not writable'}), 500
            
            # Save the task as pending
            save_task(task_id, {
                'status': 'pending',
                'progress': 0,
                'timestamp': time.time()
            })
            
            file.save(temp_path)
            
            # Check if file is empty
            if os.path.getsize(temp_path) == 0:
                os.remove(temp_path)
                save_task(task_id, {
                    'status': 'error',
                    'error': 'Uploaded file is empty',
                    'timestamp': time.time()
                })
                return jsonify({'error': 'Uploaded file is empty'}), 400
            
            # Start conversion in a background thread
            conversion_thread = threading.Thread(
                target=convert_audio,
                args=(temp_path, app.config['CONVERTED_FOLDER'], task_id)
            )
            conversion_thread.daemon = True
            conversion_thread.start()
            
            logger.info(f"Started conversion for task {task_id}")
            
            return jsonify({'task_id': task_id})
        except Exception as e:
            logger.error(f"Exception during file upload: {e}")
            return jsonify({'error': 'An internal error occurred.'}), 500

@app.route('/status/<task_id>')
def check_status(task_id):
    # Get task from file
    tasks = get_tasks()
    
    if task_id not in tasks:
        logger.warning(f"Task ID not found: {task_id}")
        return jsonify({'status': 'unknown'})
    
    return jsonify(tasks[task_id])

@app.route('/download/<task_id>')
def download_file(task_id):
    # Get task from file
    tasks = get_tasks()
    
    if task_id not in tasks or tasks[task_id]['status'] != 'complete':
        return jsonify({'error': 'File not found or conversion not complete'}), 404
        
    file_path = tasks[task_id]['output_path']
    
    if not os.path.exists(file_path):
        logger.error(f"Output file does not exist: {file_path}")
        save_task(task_id, {
            'status': 'error',
            'error': 'Output file not found on server',
            'timestamp': time.time()
        })
        return jsonify({'error': 'Output file not found on server'}), 404
    
    directory = os.path.dirname(file_path)
    filename = os.path.basename(file_path)
    
    # Schedule cleanup of the task (but keep the file for now)
    def cleanup_status():
        time.sleep(300)  # 5 minutes
        delete_task(task_id)
    
    threading.Thread(target=cleanup_status, daemon=True).start()
    
    return send_from_directory(directory, filename, as_attachment=True, 
                              download_name=tasks[task_id]['filename'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)