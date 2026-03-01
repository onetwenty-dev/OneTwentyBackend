#!/usr/bin/env python3
"""
Generate realistic CGM test data and upload to OneTwenty backend
"""

import json
import random
from datetime import datetime, timedelta
import requests

# Configuration
API_BASE_URL = "http://localhost:8000/api/v1"
# You'll need to replace this with your actual JWT token after login
JWT_TOKEN = "YOUR_JWT_TOKEN_HERE"
