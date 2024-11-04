import boto3
import base64
from PIL import Image
import io

def create_thumbnail(img, width, height):
    """Create a center-cropped thumbnail"""
    # Calculate aspect ratios
    target_ratio = width / height
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # Image is wider than needed
        new_width = int(height * img_ratio)
        new_height = height
        img = img.resize((new_width, new_height))
        left = (new_width - width) // 2
        img = img.crop((left, 0, left + width, height))
    else:
        # Image is taller than needed
        new_width = width
        new_height = int(width / img_ratio)
        img = img.resize((new_width, new_height))
        top = (new_height - height) // 2
        img = img.crop((0, top, width, top + height))
    
    return img

def create_proxy(img):
    """Create a proxy image with same dimensions"""
    return img

def lambda_handler(event, context):
    # Get the s3_uri and mode from query parameters

    input_data = event.get('input', {})
    source_location = input_data.get('sourceLocation', {})
    
    bucket = source_location.get('bucket')
    key = source_location.get('path')
    
    # Get the output bucket from event
    output_bucket = event.get('output_bucket')
    
    mode = event.get('mode',  'proxy')  # default to proxy mode
    
    if not key:
        return {
            'statusCode': 400,
            'body': 'Missing key parameter'
        }
    if not bucket:
        return {
            'statusCode': 400,
            'body': 'Missing bucket parameter'
        }
    
    if not output_bucket:
        return {
            'statusCode': 400,
            'body': 'Missing output_bucket parameter'
        }


    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Fetch the image from S3
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        image_data = s3_response['Body'].read()
        img = Image.open(io.BytesIO(image_data))

        if mode == 'thumbnail':
            # Get thumbnail parameters
            params = event.get('thumbnail')
            width = event.get('width', 100)
            height = event.get('height', 100)
            
            # Process image
            processed_img = create_thumbnail(img, width, height)
            # Generate output key
            output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_thumbnails_{width}x{height}.webp"
            
        elif mode == 'proxy':
            # Process image
            processed_img = create_proxy(img)
            width, height = img.size
            # Generate output key
            output_key = f"{bucket}/{key.rsplit('.', 1)[0]}_proxy.webp"
            
        else:
            return {'statusCode': 400, 'body': 'Invalid mode parameter'}

        # Save the processed image
        output_buffer = io.BytesIO()
        
        # Save as WebP with appropriate quality
        if mode == 'thumbnail':
            processed_img.save(output_buffer, format='WEBP', quality=85)
        else:  # proxy mode
            processed_img.save(output_buffer, format='WEBP', quality=90)
            
        output_data = output_buffer.getvalue()

        # Upload to output bucket
        s3.put_object(
            Bucket=output_bucket,
            Key=output_key,
            Body=output_data,
            ContentType='image/webp'
        )

        # Return the processed image information
        return {
            'statusCode': 200,
            'body': {
                'location':{
                    'bucket': output_bucket,
                    'key': output_key,
                },
                'width': width,
                'height': height,
                'mode': mode,
                'format': 'webp'
            }
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': f'Error processing image: {str(e)}'
        }