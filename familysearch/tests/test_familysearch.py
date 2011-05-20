import familysearch
import os.path
import unittest
import urllib2
import wsgi_intercept
import wsgi_intercept.httplib_intercept
try:
    import json
except ImportError:
    import simplejson as json

try:
    import pkg_resources
    sample_person1 = pkg_resources.resource_string(__name__, 'person1.json')
    sample_person2 = pkg_resources.resource_string(__name__, 'person2.json')
    sample_login = pkg_resources.resource_string(__name__, 'login.json')
except ImportError:
    data_dir = os.path.dirname(__file__)
    sample_person1 = open(os.path.join(data_dir, 'person1.json')).read()
    sample_person2 = open(os.path.join(data_dir, 'person2.json')).read()
    sample_login = open(os.path.join(data_dir, 'login.json')).read()

class TestFamilySearch(unittest.TestCase):

    default_headers = {'Content-Type': 'application/json'}

    def setUp(self):
        self.longMessage = True
        self.agent = 'TEST_USER_AGENT'
        self.key = 'FAKE_DEV_KEY'
        self.session = 'FAKE_SESSION_ID'
        self.username = 'FAKE_USERNAME'
        self.password = 'FAKE_PASSWORD'
        self.cookie = 'FAKE_COOKIE=FAKE_VALUE'
        wsgi_intercept.httplib_intercept.install()

    def tearDown(self):
        self.clear_request_intercpets()
        wsgi_intercept.httplib_intercept.uninstall()

    def add_request_intercept(self, response, out_environ=None, status='200 OK',
                              host='www.dev.usys.org', port=80,
                              headers=default_headers):
        '''Globally install a request intercept returning the provided response.'''
        if out_environ is None:
            out_environ = {}
        def mock_app(environ, start_response):
            out_environ.update(environ)
            start_response(status, dict(headers).items())
            return iter(response)
        wsgi_intercept.add_wsgi_intercept(host, port, lambda: mock_app)
        return out_environ

    def clear_request_intercpets(self):
        '''Remove all installed request intercepts.'''
        wsgi_intercept.remove_wsgi_intercept()

    def test_requires_user_agent(self):
        self.assertRaises(TypeError, familysearch.FamilySearch, key=self.key)

    def test_requires_dev_key(self):
        self.assertRaises(TypeError, familysearch.FamilySearch, agent=self.agent)

    def test_accepts_user_agent_and_dev_key(self):
        familysearch.FamilySearch(agent=self.agent, key=self.key)

    def test_changes_base(self):
        self.add_request_intercept(sample_person1, host='www.dev.usys.org', port=80)
        self.add_request_intercept(sample_person2, host='api.familysearch.org', port=443)
        fs_dev = familysearch.FamilySearch(self.agent, self.key)
        fs_prod = familysearch.FamilySearch(self.agent, self.key, base='https://api.familysearch.org')
        person1 = fs_dev.person()
        person2 = fs_prod.person()
        self.assertNotEqual(person1, person2, 'base argument failed to change base URL')
        self.assertEqual(person1['id'], json.loads(sample_person1)['persons'][0]['id'], 'wrong person returned from default base')
        self.assertEqual(person2['id'], json.loads(sample_person2)['persons'][0]['id'], 'wrong person returned from production base')

    def test_includes_user_agent(self):
        request_environ = self.add_request_intercept(sample_person1)
        fs = familysearch.FamilySearch(self.agent, self.key)
        fs.person()
        self.assertIn(self.agent, fs.agent, 'user agent not included in internal user agent')
        self.assertIn('HTTP_USER_AGENT', request_environ, 'user agent header not included in request')
        self.assertIn(self.agent, request_environ['HTTP_USER_AGENT'], 'user agent not included in user agent header')

    def test_restoring_session_sets_logged_in(self):
        fs = familysearch.FamilySearch(self.agent, self.key)
        self.assertFalse(fs.logged_in, 'should not be logged in by default')
        fs = familysearch.FamilySearch(self.agent, self.key, session=self.session)
        self.assertTrue(fs.logged_in, 'should be logged in after restoring session')

    def test_username_and_password_set_logged_in(self):
        self.add_request_intercept(sample_login)
        fs = familysearch.FamilySearch(self.agent, self.key, self.username, self.password)
        self.assertTrue(fs.logged_in, 'should be logged in after providing username and password')

    def test_requests_json_format(self):
        request_environ = self.add_request_intercept(sample_person1)
        fs = familysearch.FamilySearch(self.agent, self.key, session=self.session)
        fs.person()
        self.assertIn('QUERY_STRING', request_environ, 'query string not included in request')
        self.assertIn('dataFormat=application%2Fjson', request_environ['QUERY_STRING'], 'dataFormat not included in query string')

    def test_not_logged_in_if_error_401(self):
        self.add_request_intercept('', status='401 Unauthorized')
        fs = familysearch.FamilySearch(self.agent, self.key, session=self.session)
        self.assertTrue(fs.logged_in, 'should be logged in after restoring session')
        self.assertRaises(urllib2.HTTPError, fs.person)
        self.assertFalse(fs.logged_in, 'should not be logged after receiving error 401')

    def test_passes_cookies_back(self):
        fs = familysearch.FamilySearch(self.agent, self.key)

        # First request sets a cookie
        headers = self.default_headers.copy()
        headers['Set-Cookie'] = self.cookie + '; Path=/'
        self.add_request_intercept(sample_login, headers=headers)
        fs.login(self.username, self.password)

        # Second request should receive the cookie back
        request_environ = self.add_request_intercept(sample_person1)
        fs.person()
        self.assertIn('HTTP_COOKIE', request_environ, 'cookie header not included in request')
        self.assertIn(self.cookie, request_environ['HTTP_COOKIE'], 'previously-set cookie not included in cookie header')

if __name__ == '__main__':
    unittest.main()
