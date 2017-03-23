# Freesound keys for download script
# Get credentials at http://www.freesound.org/apiv2/apply
# Set callback url to https://www.freesound.org/home/app_permissions/permission_granted/
FS_CLIENT_ID = 'FREESOUND_KEY'
FS_CLIENT_SECRET = 'FREESOUND_SECRET'

# Freesound keys for "login with" functionality
# Get credentials at http://www.freesound.org/apiv2/apply
# Set callback url to http://localhost:8000/social/complete/freesound/
SOCIAL_AUTH_FREESOUND_KEY = None'
SOCIAL_AUTH_FREESOUND_SECRET = 'FREESOUND_SECRET'

# Google keys for "login with" functionality
# Get credentials at https://console.developers.google.com
# Set callback url to http://localhost:8000/social/complete/google-oauth2/
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = None  # (remove the part starting with the dot .)
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = 'GOOGLE_SECRET'

# Facebook keys for "login with" functionality
# See instructions in https://simpleisbetterthancomplex.com/tutorial/2016/10/24/how-to-add-social-login-to-django.html
# NOTE: might not work in localhost
SOCIAL_AUTH_FACEBOOK_KEY = None
SOCIAL_AUTH_FACEBOOK_SECRET = 'FACEBOOK_SECRET'

# Github keys for "login with" functionality
# Get credentials at https://github.com/settings/applications/new
# Set callback url to http://localhost:8000/social/complete/github/
SOCIAL_AUTH_GITHUB_KEY = None
SOCIAL_AUTH_GITHUB_SECRET = 'GITHUB_SECRET'
