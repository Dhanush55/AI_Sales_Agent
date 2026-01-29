import requests
import sys
import json
from datetime import datetime
import time

class VoiceSalesAgentTester:
    def __init__(self, base_url="https://leadconvo-1.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.user_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.campaign_id = None
        self.lead_id = None
        self.call_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return True, response.json() if response.text else {}
                except:
                    return True, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text}")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, response = self.run_test(
            "Root Endpoint",
            "GET",
            "",
            200
        )
        return success

    def test_user_registration(self):
        """Test user registration"""
        test_user_data = {
            "email": f"test_user_{datetime.now().strftime('%H%M%S')}@example.com",
            "password": "TestPass123!",
            "company_name": "Test Automotive Company"
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=test_user_data
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.user_id = response['user']['id']
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_user_login(self):
        """Test user login with existing credentials"""
        # First register a user
        test_email = f"login_test_{datetime.now().strftime('%H%M%S')}@example.com"
        register_data = {
            "email": test_email,
            "password": "TestPass123!",
            "company_name": "Login Test Company"
        }
        
        # Register
        success, _ = self.run_test(
            "User Registration for Login Test",
            "POST",
            "auth/register",
            200,
            data=register_data
        )
        
        if not success:
            return False
        
        # Now test login
        login_data = {
            "email": test_email,
            "password": "TestPass123!"
        }
        
        success, response = self.run_test(
            "User Login",
            "POST",
            "auth/login",
            200,
            data=login_data
        )
        
        if success and 'access_token' in response:
            # Update token for subsequent tests
            self.token = response['access_token']
            self.user_id = response['user']['id']
            return True
        return False

    def test_campaign_creation_all_languages(self):
        """Test campaign creation with all supported languages"""
        languages = ["indian_english", "hindi", "kannada", "tamil"]
        success_count = 0
        
        for lang in languages:
            campaign_data = {
                "name": f"Test Campaign {lang.title()}",
                "goal": f"Qualify leads for automotive workshop machinery in {lang.replace('_', ' ')}",
                "language": lang
            }
            
            success, response = self.run_test(
                f"Create Campaign ({lang})",
                "POST",
                "campaigns",
                200,
                data=campaign_data
            )
            
            if success and 'id' in response:
                if not self.campaign_id:  # Store first campaign for other tests
                    self.campaign_id = response['id']
                success_count += 1
        
        return success_count == len(languages)

    def test_get_campaigns(self):
        """Test getting user campaigns"""
        success, response = self.run_test(
            "Get Campaigns",
            "GET",
            "campaigns",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} campaigns")
            return True
        return False

    def test_get_specific_campaign(self):
        """Test getting a specific campaign"""
        if not self.campaign_id:
            print("❌ No campaign ID available for test")
            return False
        
        success, response = self.run_test(
            "Get Specific Campaign",
            "GET",
            f"campaigns/{self.campaign_id}",
            200
        )
        
        return success and 'id' in response

    def test_lead_creation(self):
        """Test lead creation"""
        if not self.campaign_id:
            print("❌ No campaign ID available for lead creation")
            return False
        
        lead_data = {
            "name": "Test Lead Customer",
            "phone": "+91-9876543210",
            "campaign_id": self.campaign_id
        }
        
        success, response = self.run_test(
            "Create Lead",
            "POST",
            "leads",
            200,
            data=lead_data
        )
        
        if success and 'id' in response:
            self.lead_id = response['id']
            return True
        return False

    def test_get_leads(self):
        """Test getting leads"""
        success, response = self.run_test(
            "Get Leads",
            "GET",
            "leads",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} leads")
            return True
        return False

    def test_get_leads_by_campaign(self):
        """Test getting leads filtered by campaign"""
        if not self.campaign_id:
            print("❌ No campaign ID available for filtered leads test")
            return False
        
        success, response = self.run_test(
            "Get Leads by Campaign",
            "GET",
            f"leads?campaign_id={self.campaign_id}",
            200
        )
        
        return success and isinstance(response, list)

    def test_test_mode_conversation(self):
        """Test the AI conversation flow in test mode"""
        if not self.campaign_id:
            print("❌ No campaign ID available for test mode")
            return False
        
        # Test 1: Start new conversation
        conversation_data = {
            "campaign_id": self.campaign_id,
            "user_input": "Hello, I'm interested in your machinery",
            "call_id": None,
            "simulate": None
        }
        
        success, response = self.run_test(
            "Test Mode - Start Conversation",
            "POST",
            "test-mode/chat",
            200,
            data=conversation_data
        )
        
        if not success or 'call_id' not in response:
            return False
        
        self.call_id = response['call_id']
        print(f"   Call ID: {self.call_id}")
        print(f"   Agent Response: {response.get('agent_response', 'No response')}")
        
        # Test 2: Continue conversation
        conversation_data = {
            "campaign_id": self.campaign_id,
            "user_input": "Yes, I need a tyre changer for my workshop",
            "call_id": self.call_id,
            "simulate": None
        }
        
        success, response = self.run_test(
            "Test Mode - Continue Conversation",
            "POST",
            "test-mode/chat",
            200,
            data=conversation_data
        )
        
        if success:
            print(f"   Agent Response: {response.get('agent_response', 'No response')}")
        
        # Test 3: Simulate user being busy
        conversation_data = {
            "campaign_id": self.campaign_id,
            "user_input": "I'm busy right now, can you call later?",
            "call_id": self.call_id,
            "simulate": None
        }
        
        success_busy, response_busy = self.run_test(
            "Test Mode - User Busy",
            "POST",
            "test-mode/chat",
            200,
            data=conversation_data
        )
        
        if success_busy:
            print(f"   Agent Response: {response_busy.get('agent_response', 'No response')}")
            print(f"   Should End Call: {response_busy.get('should_end_call', False)}")
        
        return success and success_busy

    def test_simulation_features(self):
        """Test simulation features (silence, interruption)"""
        if not self.campaign_id:
            print("❌ No campaign ID available for simulation test")
            return False
        
        # Start new conversation for simulation
        conversation_data = {
            "campaign_id": self.campaign_id,
            "user_input": "Hi there",
            "call_id": None,
            "simulate": None
        }
        
        success, response = self.run_test(
            "Simulation - Start New Call",
            "POST",
            "test-mode/chat",
            200,
            data=conversation_data
        )
        
        if not success:
            return False
        
        call_id = response['call_id']
        
        # Test silence simulation
        silence_data = {
            "campaign_id": self.campaign_id,
            "user_input": "",
            "call_id": call_id,
            "simulate": "silence"
        }
        
        success_silence, response_silence = self.run_test(
            "Simulation - Silence",
            "POST",
            "test-mode/chat",
            200,
            data=silence_data
        )
        
        # Test interruption simulation
        interruption_data = {
            "campaign_id": self.campaign_id,
            "user_input": "Wait, let me ask something",
            "call_id": call_id,
            "simulate": "interruption"
        }
        
        success_interruption, response_interruption = self.run_test(
            "Simulation - Interruption",
            "POST",
            "test-mode/chat",
            200,
            data=interruption_data
        )
        
        return success_silence and success_interruption

    def test_calls_api(self):
        """Test calls API endpoints"""
        success, response = self.run_test(
            "Get Calls",
            "GET",
            "calls",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} calls")
            return True
        return False

    def test_call_details(self):
        """Test getting call details if call exists"""
        if not self.call_id:
            print("❌ No call ID available for call details test")
            return True  # Skip this test
        
        success, response = self.run_test(
            "Get Call Details",
            "GET",
            f"calls/{self.call_id}",
            200
        )
        
        return success

    def test_authentication_protection(self):
        """Test that protected endpoints require authentication"""
        # Save current token
        original_token = self.token
        self.token = None
        
        # Try to access protected endpoint without token
        success, response = self.run_test(
            "Protected Endpoint Without Auth",
            "GET",
            "campaigns",
            401  # Should return unauthorized
        )
        
        # Restore token
        self.token = original_token
        
        return success

def main():
    print("🚀 Starting Voice Sales Agent API Testing")
    print("=" * 50)
    
    tester = VoiceSalesAgentTester()
    
    # Test sequence
    tests = [
        ("Root Endpoint", tester.test_root_endpoint),
        ("User Registration", tester.test_user_registration),
        ("User Login", tester.test_user_login),
        ("Authentication Protection", tester.test_authentication_protection),
        ("Campaign Creation (All Languages)", tester.test_campaign_creation_all_languages),
        ("Get Campaigns", tester.test_get_campaigns),
        ("Get Specific Campaign", tester.test_get_specific_campaign),
        ("Lead Creation", tester.test_lead_creation),
        ("Get Leads", tester.test_get_leads),
        ("Get Leads by Campaign", tester.test_get_leads_by_campaign),
        ("Test Mode Conversation", tester.test_test_mode_conversation),
        ("Simulation Features", tester.test_simulation_features),
        ("Calls API", tester.test_calls_api),
        ("Call Details", tester.test_call_details),
    ]
    
    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*20} {test_name} {'='*20}")
            if not test_func():
                failed_tests.append(test_name)
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {str(e)}")
            failed_tests.append(test_name)
    
    # Print final results
    print(f"\n{'='*60}")
    print(f"📊 FINAL RESULTS")
    print(f"{'='*60}")
    print(f"Tests Run: {tester.tests_run}")
    print(f"Tests Passed: {tester.tests_passed}")
    print(f"Tests Failed: {tester.tests_run - tester.tests_passed}")
    print(f"Success Rate: {(tester.tests_passed/tester.tests_run)*100:.1f}%")
    
    if failed_tests:
        print(f"\n❌ Failed Tests:")
        for test in failed_tests:
            print(f"   - {test}")
    else:
        print(f"\n✅ All tests passed!")
    
    return 0 if len(failed_tests) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())