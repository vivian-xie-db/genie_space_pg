import requests
import threading
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
load_dotenv(override=True)

logger = logging.getLogger(__name__)

class TokenMinter:
    """
    A class to handle OAuth token generation and renewal for Databricks.
    Automatically refreshes the token before it expires.
    Uses a reentrant lock for better concurrency.
    """
    def __init__(self, client_id: str, client_secret: str, host: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.host = host
        self.token = None
        self.expiry_time = None
        self.lock = threading.RLock()  # Use reentrant lock
        self._refresh_token()
        
    def _refresh_token(self) -> None:
        """Internal method to refresh the OAuth token"""
        url = f"https://{self.host}/oidc/v1/token"
        auth = (self.client_id, self.client_secret)
        data = {'grant_type': 'client_credentials', 'scope': 'all-apis'}
        
        try:
            response = requests.post(url, auth=auth, data=data, timeout=10)
            response.raise_for_status()
            token_data = response.json()
            
            with self.lock:
                self.token = token_data.get('access_token')
                # Set expiry time to 55 minutes (slightly less than the 60-minute expiry)
                self.expiry_time = datetime.now() + timedelta(minutes=55)
                
            logger.info("Successfully refreshed Databricks OAuth token")
        except Exception as e:
            logger.error(f"Failed to refresh Databricks OAuth token: {str(e)}")
            raise
    
    def _needs_refresh(self) -> bool:
        """Check if token needs refresh without holding the lock"""
        return (not self.token or 
                not self.expiry_time or 
                datetime.now() + timedelta(minutes=5) >= self.expiry_time)
    
    def get_token(self) -> str:
        """
        Get a valid token, refreshing if necessary.
        Uses a reentrant lock to allow nested calls.
        
        Returns:
            str: The current valid OAuth token
        """
        # First check without lock if refresh is needed
        if self._needs_refresh():
            # Only acquire lock if we need to refresh
            with self.lock:
                # Double-check pattern to avoid race conditions
                if self._needs_refresh():
                    self._refresh_token()
        return self.token

tokenminter = TokenMinter(
    client_id=os.getenv("DATABRICKS_CLIENT_ID"),
    client_secret=os.getenv("DATABRICKS_CLIENT_SECRET"),
    host=os.getenv("DATABRICKS_HOST")
)