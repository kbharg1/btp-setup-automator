from subprocess import run, PIPE
from libs.python.helperLog import logtype
from libs.python.helperJson import convertStringToJson, getJsonFromFile
import sys
import time
import os


def runShellCommand(btpUsecase, command, format, info):
    return runShellCommandFlex(btpUsecase, command, format, info, True, False)


def login_cf(btpUsecase):
    accountMetadata = btpUsecase.accountMetadata

    org = accountMetadata["org"]
    usecaseRegion = btpUsecase.region
    myemail = btpUsecase.myemail
    password = btpUsecase.mypassword

    command = None
    if btpUsecase.loginmethod == "sso":
        command = "cf login -a \"https://api.cf." + usecaseRegion + \
            ".hana.ondemand.com\" -o \"" + org + "\" --sso"
    else:
        command = "cf login -a \"https://api.cf." + usecaseRegion + \
            ".hana.ondemand.com\" -o \"" + org + "\" -u \"" + \
            myemail + "\" -p \"" + password + "\""
    # If a space is already there, attach the space name to the login to target the space
    if "cfspacename" in accountMetadata and accountMetadata["cfspacename"] is not None and accountMetadata["cfspacename"] != "":
        command = "cf target -s " + accountMetadata["cfspacename"]
        # if btpUsecase.loginmethod == "sso":
        #     command = "cf login -a \"https://api.cf." + usecaseRegion + ".hana.ondemand.com\" -o \"" + org + "\" -s \"" + accountMetadata["cfspacename"] + "\" --sso"
        # else:
        #     command = "cf login -a \"https://api.cf." + usecaseRegion + ".hana.ondemand.com\" -o \"" + org + "\" -s \"" + accountMetadata["cfspacename"] + "\" -u \"" + myemail + "\" -p \"" + password + "\""
    runShellCommandFlex(btpUsecase, command, logtype.INFO, "Logging-in to your CF environment in the org >" +
                        org + "< for your user >" + myemail + "<", True, True)


def login_btp(btpUsecase):
    myemail = btpUsecase.myemail
    password = btpUsecase.mypassword
    globalaccount = btpUsecase.globalaccount

    command = "btp login --url \"https://cpcli.cf.eu10.hana.ondemand.com\" --subdomain \"" + globalaccount + "\""
    if btpUsecase.loginmethod == "sso":
        message = "Logging-in to your global account with subdomain ID >" + globalaccount + "<"
        command = command + " --sso"
        runShellCommandFlex(btpUsecase, command, logtype.INFO, message, True, True)
        fetchEmailAddressFromBtpConfigFile(btpUsecase)
    else:
        message = "Logging-in to your global account with subdomain ID >" + globalaccount + "< for your user >" + myemail + "<"
        command = command + " --user \"" + myemail + "\" --password \"" + password + "\""
        runShellCommandFlex(btpUsecase, command, logtype.INFO, message, True, False)


def fetchEmailAddressFromBtpConfigFile(btpUsecase):
    btpConfigFile = os.environ['BTP_CLIENTCONFIG']
    jsonResult = getJsonFromFile(btpUsecase, btpConfigFile)
    if "Authentication" in jsonResult and "Mail" in jsonResult["Authentication"]:
        btpUsecase.myemail = jsonResult["Authentication"]["Mail"]
        return btpUsecase.myemail
    return None


def runShellCommandFlex(btpUsecase, command, format, info, exitIfError, noPipe):
    log = btpUsecase.log
    if info is not None:
        log.write(format, info)

    # Check whether we are calling a btp or cf command
    # If yes, we should initiate first a re-login, if necessary
    checkIfReLoginNecessary(btpUsecase, command)

    foundPassword = False
    if btpUsecase.logcommands is True:
        # Avoid to show any passwords in the log
        passwordStrings = ["password ", " -p ", " --p "]
        for passwordString in passwordStrings:
            if passwordString in command:
                commandToBeLogged = command[0:command.index(
                    passwordString) + len(passwordString) + 1] + "xxxxxxxxxxxxxxxxx"
                log.write(logtype.COMMAND, commandToBeLogged)
                foundPassword = True
                break
        if foundPassword is False:
            log.write(logtype.COMMAND, command)
    p = None
    if noPipe is True:
        p = run(command, shell=True)
    else:
        p = run(command, shell=True, stdout=PIPE, stderr=PIPE)
        output = p.stdout.decode()
        error = p.stderr.decode()
    returnCode = p.returncode

    if (returnCode == 0 or exitIfError is False):
        return p
    else:
        if p is not None and p.stdout is not None:
            output = p.stdout.decode()
            error = p.stderr.decode()
            log.write(logtype.ERROR, output)
            log.write(logtype.ERROR, error)
        else:
            log.write(logtype.ERROR, "Something went wrong, but the script can not fetch the error message. Please check the log messages before.")
        sys.exit(returnCode)


def checkIfReLoginNecessary(btpUsecase, command):
    log = btpUsecase.log
    # time in seconds for re-login
    ELAPSEDTIMEFORRELOGIN = 45 * 60

    reLogin = False
    elapsedTime = 0
    currentTime = time.time()

    if command[0:9] == "btp login":
        btpUsecase.timeLastCliLogin = currentTime
        return None

    if command[0:8] == "cf login":
        btpUsecase.timeLastCliLogin = currentTime
        return None

    if btpUsecase.timeLastCliLogin is None:
        btpUsecase.timeLastCliLogin = currentTime

    elapsedTime = currentTime - btpUsecase.timeLastCliLogin

    if elapsedTime > ELAPSEDTIMEFORRELOGIN:
        reLogin = True
    else:
        reLogin = False

    if command[0:4] == "btp " and command[0:9] != "btp login" and reLogin is True:
        minutesPassed = "{:.2f}".format(elapsedTime / 60)
        log.write(logtype.WARNING, "executing a re-login in SAP btp CLI and CF CLI as the last login happened more than >" +
                  minutesPassed + "< minutes ago")
        login_btp(btpUsecase)
        login_cf(btpUsecase)
        btpUsecase.timeLastCliLogin = currentTime

    if command[0:3] == "cf " and command[0:8] != "cf login" and reLogin is True:
        minutesPassed = "{:.2f}".format(elapsedTime / 60)
        log.write(logtype.WARNING, "executing a re-login in SAP btp CLI and CF CLI as the last login happened more than >" +
                  minutesPassed + "< minutes ago")
        login_btp(btpUsecase)
        login_cf(btpUsecase)
        btpUsecase.timeLastCliLogin = currentTime


def runCommandAndGetJsonResult(btpUsecase, command, format, message):
    p = runShellCommand(btpUsecase, command, format, message)
    list = p.stdout.decode()
    list = convertStringToJson(list)
    return list


def executeCommandsFromUsecaseFile(btpUsecase, message, jsonSection):
    log = btpUsecase.log
    usecaseDefinition = getJsonFromFile(btpUsecase, btpUsecase.usecasefile)

    if jsonSection in usecaseDefinition and len(usecaseDefinition[jsonSection]) > 0:
        commands = usecaseDefinition[jsonSection]
        log.write(logtype.HEADER, message)

        for command in commands:
            message = command["description"]
            thisCommand = command["command"]
            log.write(logtype.HEADER, "COMMAND EXECUTION: " + message)
            p = runShellCommand(btpUsecase, thisCommand, logtype.INFO, "Executing the following commands:\n" + thisCommand + "\n")
            result = p.stdout.decode()
            log.write(logtype.SUCCESS, result)
