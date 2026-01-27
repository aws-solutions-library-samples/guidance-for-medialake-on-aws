from typing import Dict, Optional

from url_utils import generate_presigned_url, generate_presigned_download_url

def enrich_asset_for_public_access(asset: Dict, settings: Dict) -> Dict:
    """Generate presigned viewing URL and filter asset data for public access"""
    
    view_url = None

    # Always use proxy representation first
    for rep in asset.get('DerivedRepresentations', []):
        if rep.get('Purpose') == 'proxy':
            storage = rep.get('StorageInfo', {}).get('PrimaryLocation', {})
            view_url = generate_presigned_url(
                bucket=storage['Bucket'],
                key=storage['ObjectKey']['FullPath']
            )
            break
        
    # Fallback to original if proxy not available
    if not view_url:
        main_storage = asset['DigitalSourceAsset']['MainRepresentation']['StorageInfo']['PrimaryLocation']
        view_url = generate_presigned_url(
            bucket=main_storage['Bucket'],
            key=main_storage['ObjectKey']['FullPath']
        )
    
    # Build filtered response
    public_asset = {
        'InventoryID': asset['InventoryID'],
        'DigitalSourceAsset': {
            'Type': asset['DigitalSourceAsset']['Type'],
            'MainRepresentation': {
                'Format': asset['DigitalSourceAsset']['MainRepresentation']['Format'],
                'StorageInfo': {
                    'PrimaryLocation': {
                        'ObjectKey': {
                            'Name': asset['DigitalSourceAsset']['MainRepresentation']['StorageInfo']['PrimaryLocation']['ObjectKey']['Name']
                        }
                    }
                }
            }
        },
        'viewUrl': view_url,
    }
    
    # Include full metadata if allowed
    if settings.get('allowMetadata'):
        public_asset['Metadata'] = asset.get('Metadata', {})
    
    return public_asset

