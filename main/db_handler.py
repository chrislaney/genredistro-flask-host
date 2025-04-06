# db_handler.py
import boto3
import uuid
from datetime import datetime
from decimal import Decimal
import json, os
from boto3.dynamodb.conditions import Key

class DynamoDBHandler:
    """
    Handler class for AWS DynamoDB operations.
    This class manages all interactions with DynamoDB for storing and retrieving user data.
    """
    
    def __init__(self, region_name='us-east-1', aws_access_key='YOUR_AWS_ACCESS_KEY', aws_secret_key='YOUR_AWS_SECRET_KEY'):
        """
        Initialize the DynamoDB handler with hardcoded AWS credentials.
        
        Args:
            region_name (str): AWS region name where DynamoDB is located
            aws_access_key (str): AWS access key ID
            aws_secret_key (str): AWS secret access key
        """
        # Use hardcoded credentials
        self.dynamodb = boto3.resource(
            'dynamodb',
            region_name=region_name,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
        self.users_table = self.dynamodb.Table('SpotifyUsers')
        self.playlists_table = self.dynamodb.Table('UserPlaylists')
        self.tracks_table = self.dynamodb.Table('UserTracks')
    
    @staticmethod
    def _convert_floats_to_decimal(obj):
        """
        Convert float values to Decimal for DynamoDB compatibility.
        
        Args:
            obj: Input object (dict, list, or primitive)
            
        Returns:
            Object with floats converted to Decimal
        """
        if isinstance(obj, dict):
            return {k: DynamoDBHandler._convert_floats_to_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [DynamoDBHandler._convert_floats_to_decimal(i) for i in obj]
        elif isinstance(obj, float):
            return Decimal(str(obj))
        elif isinstance(obj, int):
            return obj
        else:
            return obj
    
    def create_tables_if_not_exist(self):
        """
        Create the required DynamoDB tables if they don't already exist.
        """
        existing_tables = [table.name for table in self.dynamodb.tables.all()]
        
        # Create Users table if it doesn't exist
        if 'SpotifyUsers' not in existing_tables:
            self.dynamodb.create_table(
                TableName='SpotifyUsers',
                KeySchema=[
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                ],
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            )
            print("Created SpotifyUsers table")
            
        # Create Tracks table if it doesn't exist
        if 'UserTracks' not in existing_tables:
            self.dynamodb.create_table(
                TableName='UserTracks',
                KeySchema=[
                    {'AttributeName': 'entry_id', 'KeyType': 'HASH'},  # Partition key
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'entry_id', 'AttributeType': 'S'},
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'UserIdIndex',
                        'KeySchema': [
                            {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                        ],
                        'Projection': {'ProjectionType': 'ALL'},
                        'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                    },
                ],
                ProvisionedThroughput={'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
            )
            print("Created UserTracks table")
        
        print("DynamoDB tables verified/created")
        return True
    
    def save_user_data(self, user_data):
        """
        Save user profile data to DynamoDB.
        
        Args:
            user_data (dict): User data from Spotify API
            
        Returns:
            dict: The saved user data
        """
        # Extract the necessary data
        user_id = user_data.get('user_id')
        
        # Convert floats to Decimal for DynamoDB compatibility
        dynamo_data = self._convert_floats_to_decimal(user_data)
        
        # Add timestamp
        dynamo_data['last_updated'] = datetime.now().isoformat()
        
        # Save to DynamoDB
        self.users_table.put_item(Item=dynamo_data)
        
        return user_data
    
    def get_user_data(self, user_id):
        """
        Retrieve user data from DynamoDB.
        
        Args:
            user_id (str): Spotify user ID
            
        Returns:
            dict: User data or None if not found
        """
        response = self.users_table.get_item(Key={'user_id': user_id})
        return response.get('Item')
    
    def save_playlist_data(self, user_id, playlist_data):
        """
        Save playlist analysis data to DynamoDB.
        
        Args:
            user_id (str): Spotify user ID
            playlist_data (dict): Analyzed playlist data
            
        Returns:
            dict: The saved playlist data
        """
        playlist_id = playlist_data['playlist_metadata']['id']
        
        # Convert floats to Decimal for DynamoDB compatibility
        dynamo_data = self._convert_floats_to_decimal(playlist_data)
        
        # Add user_id and timestamp
        dynamo_data['user_id'] = user_id
        dynamo_data['last_updated'] = datetime.now().isoformat()
        
        # Save to DynamoDB
        self.playlists_table.put_item(Item=dynamo_data)
        
        return playlist_data
    
    def get_playlist_data(self, playlist_id):
        """
        Retrieve playlist data from DynamoDB.
        
        Args:
            playlist_id (str): Spotify playlist ID
            
        Returns:
            dict: Playlist data or None if not found
        """
        response = self.playlists_table.get_item(Key={'playlist_id': playlist_id})
        return response.get('Item')
    
    def get_user_playlists(self, user_id):
        """
        Retrieve all playlists for a specific user.
        
        Args:
            user_id (str): Spotify user ID
            
        Returns:
            list: List of playlist data objects
        """
        response = self.playlists_table.query(
            IndexName='UserIdIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
        )
        return response.get('Items', [])
    
    def save_user_tracks(self, user_id, tracks_data, time_range='medium_term'):
        """
        Save a user's top tracks to DynamoDB.
        
        Args:
            user_id (str): Spotify user ID
            tracks_data (list): List of track objects
            time_range (str): Time range of the data (short_term, medium_term, long_term)
            
        Returns:
            str: The entry ID
        """
        entry_id = f"{user_id}_{time_range}"
        
        # Convert floats to Decimal for DynamoDB compatibility
        dynamo_data = {
            'entry_id': entry_id,
            'user_id': user_id,
            'time_range': time_range,
            'timestamp': datetime.now().isoformat(),
            'tracks': self._convert_floats_to_decimal(tracks_data)
        }
        
        # Save to DynamoDB
        self.tracks_table.put_item(Item=dynamo_data)
        
        return entry_id
    
    def get_user_latest_tracks(self, user_id, time_range='medium_term'):
        """
        Retrieve the most recent top tracks for a user.
        
        Args:
            user_id (str): Spotify user ID
            time_range (str): Time range of the data
            
        Returns:
            dict: Track data entry or None if not found
        """
        response = self.tracks_table.query(
            IndexName='UserIdIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id),
            FilterExpression=boto3.dynamodb.conditions.Attr('time_range').eq(time_range),
            ScanIndexForward=False,  # Sort in descending order (newest first)
            Limit=1
        )
        
        items = response.get('Items', [])
        return items[0] if items else None
    
    def delete_user_data(self, user_id):
        """
        Delete a user's data from all tables.
        
        Args:
            user_id (str): Spotify user ID
            
        Returns:
            bool: True if successful
        """
        # Delete from users table
        self.users_table.delete_item(Key={'user_id': user_id})
        
        # Delete from playlists table - need to query first
        playlists = self.get_user_playlists(user_id)
        for playlist in playlists:
            playlist_id = playlist.get('playlist_id')
            if playlist_id:
                self.playlists_table.delete_item(Key={'playlist_id': playlist_id})
        
        # Delete from tracks table - need to query first
        tracks_response = self.tracks_table.query(
            IndexName='UserIdIndex',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('user_id').eq(user_id)
        )
        
        for track_item in tracks_response.get('Items', []):
            entry_id = track_item.get('entry_id')
            if entry_id:
                self.tracks_table.delete_item(Key={'entry_id': entry_id})
        
        return True

    def get_users_from_cluster(self, cluster_id, num_users=5):
        """
        Retrieve a specified number of users from a given cluster using the cluster_id-index GSI(secondary index) .
    
        Args:
            cluster_id (int): The cluster ID to filter by.
            num_users (int): The number of users to retrieve.

        Returns:
            list: A list of user data dictionaries.
        """
        try:
            response = self.users_table.query(
                IndexName='cluster_id-index',
                KeyConditionExpression=Key('cluster_id').eq(cluster_id),
                Limit=num_users
            )
            return response.get('Items', [])
        except Exception as e:
            print(f"Error fetching users from cluster {cluster_id}: {e}")
            return []

    def get_all_users(self):
        """
        Retrieve all users from the SpotifyUsers table.
    
        Returns:
            list: List of user data dictionaries.
        """
        try:
            response = self.users_table.scan()
            users = response.get('Items', [])

            # Handle pagination (if over 1MB of data)
            while 'LastEvaluatedKey' in response:
                response = self.users_table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
                users.extend(response.get('Items', []))

            return users
        except Exception as e:
            print(f"Error scanning SpotifyUsers table: {e}")
            return []
