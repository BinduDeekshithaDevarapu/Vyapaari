import speech_recognition as sr
import requests
from io import BytesIO
import logging
from typing import Optional, Dict, List
import tempfile
import os
import subprocess
import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag
from ..config import settings

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        """Initialize voice service."""
        self.recognizer = sr.Recognizer()
        
        # Adjust recognition parameters for better accuracy
        self.recognizer.energy_threshold = 300  # Minimum audio energy to consider for recording
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 0.8  # Seconds of non-speaking audio before a phrase is considered complete
        
        # Twilio credentials for media download
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        
        # FFmpeg path
        self.ffmpeg_path = r"C:\ffmpeg\ffmpeg.exe"
        
        # Voice command shortcuts
        self.voice_shortcuts = {
            # Basic commands
            'help': ['help', 'guide', 'assist', 'commands', 'list commands'],
            'list': ['list', 'show', 'display', 'l'],
            'total': ['total', 'sum', 't'],
            
            # Product management
            'add_new_manual': ['add new -m', 'add manual', 'add products manually'],
            'add_new_barcode': ['add new -b', 'add barcode', 'add products by barcode'],
            'add_voice': ['add -v', 'add voice', 'add products by voice'],
            'change_price_manual': ['change price -m', 'update price manual', 'modify price manual'],
            'change_price_barcode': ['change price -b', 'update price barcode', 'modify price barcode'],
            
            # Order management
            'order_manual': ['order -m', 'order manual', 'create order manual'],
            'order_barcode': ['order -b', 'order barcode', 'create order barcode'],
            
            # Stock management
            'low_stock': ['low', 'low stock', 'low inventory', 'stock alert'],
            'daily_sales': ['daily', 'daily sales', 'today sales'],
            'weekly_sales': ['weekly', 'weekly sales', 'week sales'],
            
            # Creditor management
            'creditors': ['creditors', 'list creditors', 'show creditors'],
            'add_creditor': ['add creditor', 'new creditor', 'create creditor'],
            'delete_creditor': ['del creditor', 'delete creditor', 'remove creditor'],
            'pay_creditor': ['pay', 'pay creditor', 'make payment'],
            'get_credit_amount': ['get cred amount', 'check credit', 'view credit'],
            'get_total_credit': ['get total cred', 'total credit', 'all credit']
        }
        
        # Download all required NLTK data
        required_nltk_data = [
            'punkt',
            'averaged_perceptron_tagger',
            'punkt_tab'
        ]
        
        for resource in required_nltk_data:
            try:
                nltk.data.find(f'tokenizers/{resource}')
            except LookupError:
                logger.info(f"Downloading NLTK resource: {resource}")
                nltk.download(resource, quiet=True)
                logger.info(f"Successfully downloaded NLTK resource: {resource}")

    async def process_voice_message(self, audio_url: str) -> Optional[Dict]:
        """Process voice message and convert to text."""
        try:
            logger.info(f"Processing voice message from URL: {audio_url}")
            
            # Download audio file with Twilio authentication
            response = requests.get(
                audio_url,
                auth=(self.account_sid, self.auth_token),
                timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Failed to download audio: {response.status_code}")
                return None

            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(suffix='.ogg', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name
                logger.info(f"Saved audio to temporary file: {temp_path}")

            try:
                # Convert OGG to WAV using ffmpeg
                wav_path = self._convert_ogg_to_wav(temp_path)
                if not wav_path:
                    logger.error("Failed to convert OGG to WAV")
                    return None
                logger.info(f"Converted audio to WAV: {wav_path}")

                # Process audio with speech recognition
                with sr.AudioFile(wav_path) as source:
                    # Log audio file properties
                    logger.info(f"Audio file properties: {source.DURATION} seconds, {source.SAMPLE_RATE} Hz")
                    
                    # Adjust for ambient noise
                    logger.info("Adjusting for ambient noise...")
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    logger.info(f"Energy threshold: {self.recognizer.energy_threshold}")
                    
                    # Record audio
                    logger.info("Recording audio...")
                    audio_data = self.recognizer.record(source)
                    logger.info("Audio recorded successfully")
                    
                    # Recognize speech in English
                    try:
                        logger.info("Attempting speech recognition...")
                        text = self.recognizer.recognize_google(
                            audio_data,
                            language='en-IN',
                            show_all=False  # Get only the most likely result
                        )
                        logger.info(f"Successfully recognized text: {text}")

                        # Parse the text for commands and entities
                        parsed_text = self._parse_voice_text(text)
                        logger.info(f"Parsed text: {parsed_text}")

                        return {
                            'text': text,
                            'parsed': parsed_text,
                            'language': 'en-IN'
                        }
                    except sr.UnknownValueError:
                        logger.error("Speech recognition could not understand audio. This could be due to:")
                        logger.error("1. Audio is too quiet or noisy")
                        logger.error("2. Speech is unclear or mumbled")
                        logger.error("3. Audio format issues")
                        return None
                    except sr.RequestError as e:
                        logger.error(f"Could not request results from speech recognition service: {str(e)}")
                        logger.error("This could be due to:")
                        logger.error("1. Internet connection issues")
                        logger.error("2. Google Speech Recognition service being unavailable")
                        logger.error("3. API quota exceeded")
                        return None

            finally:
                # Clean up temporary files
                try:
                    os.unlink(temp_path)
                    if wav_path:
                        os.unlink(wav_path)
                    logger.info("Cleaned up temporary files")
                except Exception as e:
                    logger.error(f"Error cleaning up temporary files: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing voice message: {str(e)}")
            return None

    def _convert_ogg_to_wav(self, ogg_path: str) -> Optional[str]:
        """Convert OGG file to WAV format using ffmpeg."""
        try:
            wav_path = ogg_path.replace('.ogg', '.wav')
            logger.info(f"Converting {ogg_path} to {wav_path}")
            
            # Use subprocess to run ffmpeg with full path
            command = [
                self.ffmpeg_path,
                '-i', ogg_path,
                '-acodec', 'pcm_s16le',  # Use 16-bit PCM encoding
                '-ac', '1',              # Convert to mono
                '-ar', '16k',            # Set sample rate to 16kHz
                '-y',                    # Overwrite output file if it exists
                wav_path
            ]
            
            # Run ffmpeg command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                return None
                
            logger.info("Successfully converted OGG to WAV")
            return wav_path

        except Exception as e:
            logger.error(f"Error converting OGG to WAV: {str(e)}")
            return None

    def _parse_voice_text(self, text: str) -> Dict:
        """Parse voice text for commands and entities."""
        try:
            # Simple command matching without NLTK
            text = text.lower().strip()
            
            # Initialize result
            result = {
                'command': None,
                'action': None,
                'entities': {}
            }
            
            # Direct command matching
            for cmd, aliases in self.voice_shortcuts.items():
                if text in aliases:
                    result['command'] = cmd
                    break
            
            return result

        except Exception as e:
            logger.error(f"Error parsing voice text: {str(e)}")
            return {
                'command': None,
                'action': None,
                'entities': {}
            }

    def get_voice_shortcuts(self) -> str:
        """Get formatted list of voice shortcuts."""
        response = "🎤 *Voice Commands*\n\n"
        
        # Basic commands
        response += "*Basic Commands:*\n"
        response += "• help - Show this help menu\n"
        response += "• list - Show all products\n"
        response += "• total - Calculate total\n\n"
        
        # Product management
        response += "*Product Management:*\n"
        response += "• add new -m - Add products manually\n"
        response += "• add new -b - Add products via barcode\n"
        response += "• add -v - Add products via voice\n"
        response += "• change price -m - Change price manually\n"
        response += "• change price -b - Change price via barcode\n\n"
        
        # Order management
        response += "*Order Management:*\n"
        response += "• order -m - Create order manually\n"
        response += "• order -b - Create order via barcode\n\n"
        
        # Stock management
        response += "*Stock Management:*\n"
        response += "• low - Show low stock items\n"
        response += "• daily - Show daily sales\n"
        response += "• weekly - Show weekly sales\n\n"
        
        # Creditor management
        response += "*Creditor Management:*\n"
        response += "• creditors - List all creditors\n"
        response += "• add creditor - Add new creditor\n"
        response += "• del creditor - Delete creditor\n"
        response += "• pay - Process payment\n"
        response += "• get cred amount - Check credit amount\n"
        response += "• get total cred - Get total credit\n\n"
        
        response += "💡 *Tips for better voice recognition:*\n"
        response += "• Speak clearly and at a normal pace\n"
        response += "• Minimize background noise\n"
        response += "• Keep the phone close to your mouth\n"
        response += "• Use simple, clear commands\n"
        return response 