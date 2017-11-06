import datetime
def dwrite(contenttowrite):
    target = open("devlogfile.txt", 'a+')
    target.write("\n==========================="+str(datetime.datetime.now())+"===========================\n")
    target.write("\n"+str(contenttowrite)+"\n")
    target.close()