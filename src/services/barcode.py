from PIL import Image
import cv2
import numpy as np
import logging
from typing import Optional, List, Dict
import os
import tempfile
import requests
from io import BytesIO
import re
import time
from PIL import ImageEnhance
from ..config import settings

logger = logging.getLogger(__name__)

class BarcodeService:
    def __init__(self):
        """Initialize barcode service."""
        self.supported_formats = ['QR_CODE', 'CODE_128', 'EAN_13', 'EAN_8', 'UPC_A', 'UPC_E']
        self.max_retries = 3
        self.retry_delay = 1  # seconds
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN

    async def process_barcode(self, image_url: str) -> Optional[Dict]:
        """Process barcode image and return decoded data."""
        try:
            # Download image with Twilio authentication
            logger.info(f"Downloading image from {image_url}")
            response = requests.get(
                image_url,
                auth=(self.account_sid, self.auth_token),
                timeout=10
            )
            if response.status_code != 200:
                logger.error(f"Failed to download image: {response.status_code}")
                return None

            # Create temporary file for image
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
                temp_file.write(response.content)
                temp_path = temp_file.name

            try:
                # Read image with OpenCV
                image = cv2.imread(temp_path)
                if image is None:
                    logger.error("Failed to read image")
                    return None

                # Convert to grayscale
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

                # Apply adaptive thresholding
                thresh = cv2.adaptiveThreshold(
                    gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                    cv2.THRESH_BINARY, 11, 2
                )

                # Apply morphological operations
                kernel = np.ones((3,3), np.uint8)
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

                # Find contours
                contours, _ = cv2.findContours(
                    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                # Process each contour
                for contour in contours:
                    # Get bounding rectangle
                    x, y, w, h = cv2.boundingRect(contour)
                    
                    # Filter small contours
                    if w < 30 or h < 30:
                        continue

                    # Extract ROI
                    roi = gray[y:y+h, x:x+w]
                    
                    # Enhance ROI
                    roi = cv2.equalizeHist(roi)
                    roi = cv2.GaussianBlur(roi, (5,5), 0)
                    
                    # Try to decode with different methods
                    decoded_data = self._decode_barcode(roi)
                    if decoded_data:
                        logger.info(f"Successfully decoded barcode: {decoded_data}")
                        return {
                            'data': decoded_data,
                            'format': 'Unknown',  # We can't determine format with basic OpenCV
                            'position': {
                                'x': x,
                                'y': y,
                                'width': w,
                                'height': h
                            }
                        }

                logger.error("No barcode found in image")
                return None

            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.error(f"Error cleaning up temporary file: {str(e)}")

        except Exception as e:
            logger.error(f"Error processing barcode: {str(e)}")
            return None

    def _decode_barcode(self, image: np.ndarray) -> Optional[str]:
        """Attempt to decode barcode using basic image processing."""
        try:
            # Apply additional processing
            # 1. Denoise
            denoised = cv2.fastNlMeansDenoising(image)
            
            # 2. Enhance contrast
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 3. Try different thresholding methods
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # 4. Try to find patterns
            # Look for alternating black and white bars
            row_sums = np.sum(binary, axis=1)
            transitions = np.where(np.diff(row_sums) != 0)[0]
            
            if len(transitions) > 0:
                # Found potential barcode pattern
                # Convert to string representation
                pattern = ''.join(['1' if x > 0 else '0' for x in row_sums])
                return pattern
            
            return None

        except Exception as e:
            logger.error(f"Error decoding barcode: {str(e)}")
            return None

    def format_barcode_response(self, result: Dict) -> str:
        """Format barcode recognition result for display."""
        if not result:
            return "❌ Could not process barcode. Please try again."

        response = f"📷 *Barcode Scan*\n\n"
        response += f"Data: {result['data']}\n"
        response += f"Format: {result['format']}\n"
        response += f"Position: x={result['position']['x']}, y={result['position']['y']}\n"
        response += f"Size: {result['position']['width']}x{result['position']['height']}\n"
        
        return response

    def _enhance_image(self, image: Image.Image) -> Image.Image:
        """Enhance image for better barcode detection."""
        try:
            # Convert to grayscale
            image = image.convert('L')
            
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Enhance sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            return image
        except Exception as e:
            logger.error(f"Error enhancing image: {str(e)}")
            return image

    def _calculate_quality(self, barcode) -> float:
        """Calculate barcode quality score (0-1)."""
        try:
            # Get barcode polygon
            points = barcode.polygon
            
            # Calculate area
            area = self._polygon_area(points)
            
            # Calculate quality based on area and number of points
            quality = min(1.0, area / 1000.0)  # Normalize to 0-1
            
            # Adjust quality based on barcode type
            if barcode.type in ['EAN13', 'EAN8', 'UPC']:
                # These formats require higher quality
                quality *= 1.2
            
            return min(1.0, quality)
        except Exception as e:
            logger.error(f"Error calculating barcode quality: {str(e)}")
            return 0.0

    def _polygon_area(self, points) -> float:
        """Calculate polygon area using shoelace formula."""
        try:
            n = len(points)
            area = 0.0
            
            for i in range(n):
                j = (i + 1) % n
                area += points[i][0] * points[j][1]
                area -= points[j][0] * points[i][1]
            
            return abs(area) / 2.0
        except Exception as e:
            logger.error(f"Error calculating polygon area: {str(e)}")
            return 0.0

    def validate_barcode(self, barcode: str) -> bool:
        """Validate barcode format."""
        try:
            # Remove any non-digit characters
            barcode = re.sub(r'\D', '', barcode)
            
            # Check length
            if len(barcode) not in [8, 12, 13]:
                return False
            
            # Validate check digit for EAN-13
            if len(barcode) == 13:
                return self._validate_ean13(barcode)
            
            # Validate check digit for EAN-8
            if len(barcode) == 8:
                return self._validate_ean8(barcode)
            
            # Validate check digit for UPC
            if len(barcode) == 12:
                return self._validate_upc(barcode)
            
            return False
        except Exception as e:
            logger.error(f"Error validating barcode: {str(e)}")
            return False

    def _validate_ean13(self, barcode: str) -> bool:
        """Validate EAN-13 check digit."""
        try:
            # Calculate check digit
            total = 0
            for i in range(12):
                digit = int(barcode[i])
                if i % 2 == 0:
                    total += digit
                else:
                    total += digit * 3
            
            check_digit = (10 - (total % 10)) % 10
            
            # Compare with last digit
            return check_digit == int(barcode[-1])
        except Exception as e:
            logger.error(f"Error validating EAN-13: {str(e)}")
            return False

    def _validate_ean8(self, barcode: str) -> bool:
        """Validate EAN-8 check digit."""
        try:
            # Calculate check digit
            total = 0
            for i in range(7):
                digit = int(barcode[i])
                if i % 2 == 0:
                    total += digit * 3
                else:
                    total += digit
            
            check_digit = (10 - (total % 10)) % 10
            
            # Compare with last digit
            return check_digit == int(barcode[-1])
        except Exception as e:
            logger.error(f"Error validating EAN-8: {str(e)}")
            return False

    def _validate_upc(self, barcode: str) -> bool:
        """Validate UPC check digit."""
        try:
            # Calculate check digit
            total = 0
            for i in range(11):
                digit = int(barcode[i])
                if i % 2 == 0:
                    total += digit * 3
                else:
                    total += digit
            
            check_digit = (10 - (total % 10)) % 10
            
            # Compare with last digit
            return check_digit == int(barcode[-1])
        except Exception as e:
            logger.error(f"Error validating UPC: {str(e)}")
            return False

    def format_barcode(self, barcode: str) -> str:
        """Format barcode for display."""
        try:
            # Remove any non-digit characters
            barcode = re.sub(r'\D', '', barcode)
            
            # Format based on length
            if len(barcode) == 13:
                return f"{barcode[:1]}-{barcode[1:7]}-{barcode[7:12]}-{barcode[12]}"
            elif len(barcode) == 8:
                return f"{barcode[:4]}-{barcode[4:7]}-{barcode[7]}"
            elif len(barcode) == 12:
                return f"{barcode[:1]}-{barcode[1:6]}-{barcode[6:11]}-{barcode[11]}"
            else:
                return barcode
        except Exception as e:
            logger.error(f"Error formatting barcode: {str(e)}")
            return barcode 