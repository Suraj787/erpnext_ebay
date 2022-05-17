import datetime
def vwrite(contenttowrite):
    file_name = "vebaylogfile_%s.txt" % datetime.datetime.now().date()
    target = open(file_name, 'a+')
    target.write("\n==========================="+str(datetime.datetime.now())+"===========================\n")
    target.write("\n"+str(contenttowrite)+"\n")
    target.close()
def rwrite(contenttowrite):
    target = open("vebayreportfile.txt", 'a+')
    target.write("\n==========================="+str(datetime.datetime.now())+"===========================\n")
    target.write("\n"+str(contenttowrite)+"\n")
    target.close()
def ebaydebug(contenttowrite):
    target = open("debugebay.txt", 'a+')
    target.write("\n===========================" + str(datetime.datetime.now()) + "===========================\n")
    target.write("\n" + str(contenttowrite) + "\n")
    target.close()
def iwrite(contenttowrite):
    file_name = "vissuelogfile_%s.txt" % datetime.datetime.now().date()
    target = open(file_name, 'a+')
    target.write("\n==========================="+str(datetime.datetime.now())+"===========================\n")
    target.write("\n"+str(contenttowrite)+"\n")
    target.close()
def vissuedebug(contenttowrite):
    file_name = "vdebuglogfile_%s.txt" % datetime.datetime.now().date()
    target = open(file_name, 'a+')
    target.write("\n===========================" + str(datetime.datetime.now()) + "===========================\n")
    target.write("\n" + str(contenttowrite) + "\n")
    target.close()
