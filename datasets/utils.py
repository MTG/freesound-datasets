import os
from urllib.parse import urljoin
from django.conf import settings
from django.core.urlresolvers import reverse

def generate_download_script(dataset):
    output = """
import urllib2
import json
import sys
import cgi
import os
import time
"""
    access_token_url = urljoin(settings.BASE_URL, reverse('get_access_token'))
    output += "get_code_url = 'https://www.freesound.org/apiv2/oauth2/authorize/?response_type=code&client_id=%s'"\
            % (os.environ[settings.APP_ENV_CLIENT_ID])

    output += """
verbose = False
download_path = "fs_dataset"
progress = {"downloaded": [], "access_token": None}

print("FreesoundDataset download script")
print("--------------------------------\\n")
if len(sys.argv) > 1 and sys.argv[1] == '-v':
    verbose = True

if verbose:
    print("please, enter the location to place the downlaoded files: (default: ./fs_dataset)")
    download_path = raw_input() or 'fs_dataset'

if not os.path.exists(download_path):
    os.makedirs(download_path)

if os.path.exists(download_path+"/progress.json"):
    progress = json.load(open(download_path+"/progress.json"))

expired = True
if progress["access_token"]:
    expired = int(time.time())+5*60 > progress["curr_time"] + progress["access_token"]["expires_in"]

while expired:
    print("please, go to:")
    print(get_code_url)
    print("and copy the code here:")
    code = raw_input()

    if verbose:
        print("\\nRequesting access_token using code: %s" % code)

    # this could be done on callback:
    """

    output += "get_access_token_url = '"+access_token_url+"?code=%s' % code"

    output += """
    try:
        rsp = urllib2.urlopen(get_access_token_url)
        access_token = json.load(rsp)
        progress["access_token"] = access_token
        progress["curr_time"] = int(time.time())

        if verbose:
            print("\\nGot access_token successfully  %s" % access_token["access_token"])
        expired = False
    except urllib2.HTTPError:
            print("\\nFailed getting access_token, retrying...")

"""
    sounds = []
    for s in dataset.sounds.all():
        sounds.append("'%d': 'https://www.freesound.org/apiv2/sounds/%d/'," %
                (s.freesound_id, s.freesound_id))

    output += "sounds_dict = {"+ '\n'.join(sounds) + "}\n"

    output +="""

print("\\nStarting download of %d sounds\\n" % len(sounds_dict.keys()))

token = progress["access_token"]["access_token"]
headers = {'Authorization': 'Bearer %s' % token}
for i in sounds_dict.keys():
    if i in progress["downloaded"]:
        print("Sound %s already downloaded, skipping" % i)
        continue
    response = 'y'
    if verbose:
        print("Downloading sound: sounds_dict[i]")
        print("Do you want to download this sound? (enter: yes(y) to download or no(n) to skip)")
        reponse = raw_input()
    if response in ('y', 'yes'):
        print("Downloading... [%d/%d]" % (len(progress["downloaded"])+1, len(sounds_dict.keys())))

        req = urllib2.Request(sounds_dict[i]+"download/", headers=headers)
        with open(i, 'wb') as output:
            res = urllib2.urlopen(req)
            output.write(res.read())
        f_name = download_path + '/' + cgi.parse_header(res.headers['content-disposition'])[1]['filename']

        os.rename(i, f_name)

        req = urllib2.Request(sounds_dict[i], headers=headers)
        with open(os.path.splitext(f_name)[0]+'.json', 'wb') as output:
            output.write(urllib2.urlopen(req).read())

    progress["downloaded"].append(i)
    print("Done: %d/%d" % (len(progress["downloaded"]), len(sounds_dict.keys())))

    with open(download_path+"/progress.json", 'w') as outfile:
        json.dump(progress, outfile)
print("\\nDownload finished!")
"""
    return output
