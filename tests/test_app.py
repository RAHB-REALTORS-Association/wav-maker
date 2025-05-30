import os
import sys
import pytest
import tempfile
import json
from unittest.mock import patch, MagicMock, mock_open

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app module but manually set template/static folder before creating test client
import app


@pytest.fixture
def client():
    """Create a test client for the app."""
    # Configure app for testing
    test_app = app.app
    test_app.config['TESTING'] = True
    test_app.config['UPLOAD_FOLDER'] = tempfile.mkdtemp()
    test_app.config['CONVERTED_FOLDER'] = tempfile.mkdtemp()
    test_app.config['TASKS_FILE'] = tempfile.mktemp()
    
    # Override template and static folders
    test_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(test_dir)
    test_app.template_folder = os.path.join(repo_dir, 'test_templates')
    test_app.static_folder = os.path.join(repo_dir, 'test_static')
    
    # Create an empty tasks file
    with open(test_app.config['TASKS_FILE'], 'w') as f:
        json.dump({}, f)
    
    with test_app.test_client() as client:
        yield client
    
    # Cleanup temporary directories and files
    try:
        os.unlink(test_app.config['TASKS_FILE'])
        os.rmdir(test_app.config['UPLOAD_FOLDER'])
        os.rmdir(test_app.config['CONVERTED_FOLDER'])
    except:
        pass


def test_index_route(client):
    """Test the index route returns the expected content."""
    response = client.get('/')
    assert response.status_code == 200
    # Check for elements in the test template
    assert b'<!DOCTYPE html>' in response.data
    assert b'<html lang="en">' in response.data
    assert b'Convert' in response.data
    assert b'Audio' in response.data


def test_upload_no_file(client):
    """Test uploading with no file."""
    response = client.post('/upload')
    assert response.status_code == 400
    assert b'No file part' in response.data


def test_upload_empty_filename(client):
    """Test uploading with an empty filename."""
    response = client.post('/upload', data={'audiofile': (b'', '')})
    assert response.status_code == 400
    assert b'No selected file' in response.data


@patch('app.threading.Thread')
def test_upload_success(mock_thread, client):
    """Test successful file upload starts conversion thread."""
    # Mock the save_task function to avoid file operations
    with patch('app.save_task') as mock_save_task:
        # Create a small dummy audio file
        with tempfile.NamedTemporaryFile(suffix='.mp3') as temp_file:
            temp_file.write(b'dummy audio content')
            temp_file.flush()
            
            with open(temp_file.name, 'rb') as f:
                response = client.post(
                    '/upload',
                    data={'audiofile': (f, 'test_audio.mp3')}
                )
    
    assert response.status_code == 200
    assert 'task_id' in response.json
    mock_thread.assert_called_once()
    
    # Verify the thread was started with the correct arguments
    args, kwargs = mock_thread.call_args
    assert kwargs.get('target') == app.convert_audio


def test_status_unknown(client):
    """Test status check for unknown task ID."""
    response = client.get('/status/nonexistent-task-id')
    assert response.status_code == 200
    assert response.json['status'] == 'unknown'


@patch('app.get_file_md5')
@patch('app.os.path.exists', return_value=True)
@patch('app.os.path.getsize', return_value=1024)
@patch('app.mediainfo', return_value={'sample_rate': '44100', 'channels': '2', 'bit_depth': '16'})
@patch('app.AudioSegment')
def test_convert_audio(mock_audiosegment, mock_mediainfo, mock_getsize, mock_exists, mock_md5, client):
    """Test audio conversion function with file-based task storage."""
    # Setup mock AudioSegment
    mock_sound = MagicMock()
    mock_sound.channels = 2
    mock_sound.frame_rate = 44100
    # Set sample width to 1 (8-bit) to ensure set_sample_width gets called
    mock_sound.sample_width = 1
    
    # Setup mock for converted sound
    mock_converted = MagicMock()
    mock_converted.channels = 1
    mock_converted.frame_rate = 8000
    mock_converted.sample_width = 2
    
    # Make sure the mock returns itself after operations to allow chaining
    mock_sound.set_channels.return_value = mock_sound
    mock_sound.set_frame_rate.return_value = mock_sound
    mock_sound.set_sample_width.return_value = mock_sound
    
    # Set up side effect to return different mocks for different calls
    mock_audiosegment.from_file.side_effect = [mock_sound, mock_converted]
    
    # Set up different MD5 hashes for input and output to pass validation
    mock_md5.side_effect = ['input_hash', 'output_hash']
    
    # Mock the save_task function to avoid file operations
    mock_tasks = {}
    
    def mock_save_task_impl(task_id, task_data):
        mock_tasks[task_id] = task_data
        return True
    
    with patch('app.save_task', side_effect=mock_save_task_impl):
        # Test convert_audio function
        task_id = 'test-task-id'
        input_path = 'test_input.mp3'
        output_dir = 'test_output_dir'
        
        result = app.convert_audio(input_path, output_dir, task_id)
        
        # Check the mock tasks were updated correctly
        assert task_id in mock_tasks
        assert mock_tasks[task_id]['status'] == 'complete'
        assert mock_tasks[task_id]['progress'] == 100
        
        # Check that audio was converted with the correct parameters
        mock_sound.set_channels.assert_called_once_with(1)
        mock_sound.set_frame_rate.assert_called_once_with(8000)
        mock_sound.set_sample_width.assert_called_once_with(2)
        
        # Check that export was called with the correct parameters
        mock_sound.export.assert_called_once()
        args, kwargs = mock_sound.export.call_args
        assert kwargs['format'] == 'wav'


def test_download_nonexistent(client):
    """Test download for nonexistent file."""
    # Mock get_tasks to return no tasks
    with patch('app.get_tasks', return_value={}):
        response = client.get('/download/nonexistent-task-id')
        assert response.status_code == 404
        assert b'File not found or conversion not complete' in response.data