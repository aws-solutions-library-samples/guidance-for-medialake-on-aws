from typing import Dict, Optional

from url_utils import generate_presigned_url

def generate_presigned_url_for_embedded(asset: Dict, settings: Dict) -> Optional[str]:
    """
    Generate presigned download URL based on representation type.
    
    Args:
        asset: Asset details from DynamoDB
        settings: Share settings containing representationType
    
    Returns:
        Presigned download URL or None if representation not available
    """
    representation_type = settings.get('representationType', 'proxy')
    
    if representation_type == 'original':
        # Use original/main representation
        main_storage = asset['DigitalSourceAsset']['MainRepresentation']['StorageInfo']['PrimaryLocation']
        return generate_presigned_url(
            bucket=main_storage['Bucket'],
            key=main_storage['ObjectKey']['FullPath']
        )
    
    # For proxy representation, only return if it exists
    for rep in asset.get('DerivedRepresentations', []):
        if rep.get('Purpose') == 'proxy':
            storage = rep.get('StorageInfo', {}).get('PrimaryLocation', {})
            return generate_presigned_url(
                bucket=storage['Bucket'],
                key=storage['ObjectKey']['FullPath']
            )
    
    # No proxy representation found
    return None
