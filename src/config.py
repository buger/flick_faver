# ------------------------------------------------------------------------------
# configuration: copy this file to ``config.py`` and set these to suit your app!
# ------------------------------------------------------------------------------
 
OAUTH_APP_SETTINGS = {
 
    'twitter': {
 
        'consumer_key': '',
        'consumer_secret': '',
 
        'request_token_url': 'https://twitter.com/oauth/request_token',
        'access_token_url': 'https://twitter.com/oauth/access_token',
        'user_auth_url': 'http://twitter.com/oauth/authorize',
 
        'default_api_prefix': 'http://twitter.com',
        'default_api_suffix': '.json',
 
        },
 
    'google': {
 
        'consumer_key': '',
        'consumer_secret': '',
 
        'request_token_url': 'https://www.google.com/accounts/OAuthGetRequestToken',
        'access_token_url': 'https://www.google.com/accounts/OAuthGetAccessToken',
        'user_auth_url': 'https://www.google.com/accounts/OAuthAuthorizeToken',
 
        },
 
    }
 
CLEANUP_BATCH_SIZE = 100
 
EXPIRATION_WINDOW = 60*60*1 # 1 hour
 
STATIC_OAUTH_TIMESTAMP = 12345 # a workaround for clock skew/network lag