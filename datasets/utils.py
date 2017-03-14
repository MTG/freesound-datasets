from django.conf import settings

def generate_download_script(dataset):
    output = "import urllib2\nimport json\n"

    output += "get_code_url = 'https://test.freesound.org/apiv2/oauth2/authorize/?response_type=code&client_id=%s'\n" % (settings.APP_CLIENT_ID)

    output += """
print("please, go to:")
print(get_code_url)
print("and copy the code here:")
code = raw_input()

# this could be done on callback:
get_access_token_url = "http://localhost:8000/get-access-token/?code=%s" % code

rsp = urllib2.urlopen(get_access_token_url)
access_token = json.load(rsp)
"""

    sounds = []
    for s in dataset.sounds.all():
        sounds.append("'%d.txt': 'https://test.freesound.org/apiv2/sounds/%d/'," %
                (s.freesound_id, s.freesound_id))

    output += "sounds_dict = {"+ '\n'.join(sounds) + "}\n"

    output +="""
headers = {'Authorization': 'Bearer %s' % access_token["access_token"]}
for i in sounds_dict.keys():
    request = urllib2.Request(sounds_dict[i], headers=headers)
    with open(i,'wb') as output:
        output.write(urllib2.urlopen(request).read())
"""
    return output
