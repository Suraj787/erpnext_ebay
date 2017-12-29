YOUR_CLIENT_ID = '909547726371-lkc01ret91mahjuc6fe2k0ppcmlpuumj.apps.googleusercontent.com'
YOUR_CLIENT_SECRET = 'FV3pnlZwkr56_ykFtAxsELsa'
YOUR_SCOPE = 'https://www.googleapis.com/auth/contacts'
YOUR_APPLICATION_NAME_AND_APPLICATION_VERSION = '/'

def gist_write(feed):
    target = open("entry.xml", 'a+')
    target.write("\n"+str(feed)+"\n")
    target.close()