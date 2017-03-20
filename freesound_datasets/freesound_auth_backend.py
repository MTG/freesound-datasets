from social_core.backends.oauth import BaseOAuth2


class FreesoundOAuth2(BaseOAuth2):
    name = 'freesound'
    ID_KEY = 'unique_id'
    BASE_URL = "https://www.freesound.org/apiv2/"
    AUTHORIZATION_URL = BASE_URL + 'oauth2/logout_and_authorize/?client_id={client_id}&response_type=code&state={state}'
    ACCESS_TOKEN_URL = BASE_URL + 'oauth2/access_token/'
    REFRESH_TOKEN_URL = BASE_URL + 'oauth2/refresh_token/'
    ACCESS_TOKEN_METHOD = 'POST'
    EXTRA_DATA = [
        ('refresh_token', 'refresh_token'),
        ('expires_in', 'expires_in'),
    ]

    def auth_url(self):
        client_id, client_secret = self.get_key_and_secret()
        url = self.AUTHORIZATION_URL
        return url.format(client_id=client_id, state=self.get_or_create_state())

    def auth_complete_params(self, state=None):
        client_id, client_secret = self.get_key_and_secret()
        return {
            'grant_type': 'authorization_code',
            'code': self.data.get('code', ''),
            'client_id': client_id,
            'client_secret': client_secret,
        }

    def get_user_details(self, response):
        return response

    def user_data(self, access_token, *args, **kwargs):
        response = self.get_json(self.BASE_URL + 'me/', headers={'Authorization': 'Bearer %s' % access_token})
        return {'username': response['username'], 'email': response['email'], 'unique_id': response['unique_id']}

    def get_key_and_secret(self):
        return self.setting('SOCIAL_AUTH_FREESOUND_KEY'), self.setting('SOCIAL_AUTH_FREESOUND_SECRET')
