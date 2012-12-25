from django.test import TestCase
from django.test.client import Client

class HomeViewsTestCase(TestCase):
    fixtures = ['auth_testdata.json']

    def test_index(self):
        c = Client()
        
        response = c.post('/accounts/login/', {'username': 'test', 'password': 'test'}, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertTrue('characters' in response.context)
        self.assertTrue('corporations' in response.context)
