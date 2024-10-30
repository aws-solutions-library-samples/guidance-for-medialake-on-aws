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
    s3_uri = event.get('parameters', {}).get('s3_uri')
    mode = event.get('parameters', {}).get('mode', 'thumbnail')  # default to thumbnail mode
    
    if not s3_uri:
        return {
            'statusCode': 400,
            'body': 'Missing s3_uri parameter'
        }

    # Get the output bucket from event
    output_bucket = event.get('parameters', {}).get('output_bucket')
    if not output_bucket:
        return {
            'statusCode': 400,
            'body': 'Missing output_bucket parameter'
        }

    # Parse S3 URI
    if not s3_uri.startswith('s3://'):
        return {'statusCode': 400, 'body': 'Invalid s3_uri parameter'}
    s3_uri = s3_uri[5:]
    bucket_end = s3_uri.find('/')
    if bucket_end == -1:
        return {'statusCode': 400, 'body': 'Invalid s3_uri parameter, missing key'}
    bucket = s3_uri[:bucket_end]
    key = s3_uri[bucket_end+1:]

    # Initialize S3 client
    s3 = boto3.client('s3')

    try:
        # Fetch the image from S3
        s3_response = s3.get_object(Bucket=bucket, Key=key)
        image_data = s3_response['Body'].read()
        img = Image.open(io.BytesIO(image_data))

        if mode == 'thumbnail':
            # Get thumbnail parameters
            params = event.get('parameters', {}).get('thumbnail', {})
            width = params.get('width', 100)
            height = params.get('height', 100)
            
            # Process image
            processed_img = create_thumbnail(img, width, height)
            # Generate output key
            output_key = f"thumbnails/{key.rsplit('.', 1)[0]}_{width}x{height}.webp"
            
        elif mode == 'proxy':
            # Process image
            processed_img = create_proxy(img)
            width, height = img.size
            # Generate output key
            output_key = f"proxies/{key.rsplit('.', 1)[0]}.webp"
            
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
                'bucket': output_bucket,
                'key': output_key,
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