import boto3

def lambda_handler(event, context):
    """
    Fetches all enabled AWS regions in the account.
    """
    ec2_client = boto3.client('ec2', region_name='us-east-1')
    
    # Retrieve all active regions
    response = ec2_client.describe_regions(
        AllRegions=False  # Only fetch regions enabled for this account
    )
    
    regions = [region['RegionName'] for region in response.get('Regions', [])]
    
    print(f"Discovered {len(regions)} active AWS regions: {regions}")
    
    # Step Functions will map over this list
    return {
        "regions": regions
    }
