import requests
import time

class APIClient:
    def __init__(self, base_url, api_key):
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"x-rapidapi-key": api_key, "Content-Type": "application/json"}
        self.rate_limit_remaining = 100  # example of maximum requests per period
        self.rate_limit_reset = time.time() + 60  # reset time for rate limit

    def _handle_response(self, response):
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429:
            # Rate limit exceeded
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            time_to_wait = reset_time - time.time()
            if time_to_wait > 0:
                print(f'Rate limit exceeded. Waiting for {time_to_wait} seconds.')
                time.sleep(time_to_wait)
            return self._call_api(response.request)
        else:
            raise Exception(f'API call failed with status code {response.status_code}. Message: {response.text}')

    def _call_api(self, endpoint):
        if self.rate_limit_remaining == 0:
            time_to_wait = self.rate_limit_reset - time.time()
            if time_to_wait > 0:
                print(f'Waiting for {time_to_wait} seconds due to rate limiting.')
                time.sleep(time_to_wait)

        response = requests.get(f'{self.base_url}/{endpoint}', headers=self.headers)
        self.rate_limit_remaining -= 1
        return self._handle_response(response)

    def get_data(self, endpoint):
        return self._call_api(endpoint)
