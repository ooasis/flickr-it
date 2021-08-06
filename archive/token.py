## Import required files for this example.

import flickr,os

## The following line is a variable that holds what permission
## your program is requesting.
##   - "read"
##   - "write" (which allows read as well)
##   - "delete" (which allows read and write as well)
## are the 3 options available to you.

permission = "read"


## The following line links the class Auth() into a variable
## so that the methods within can be used.

myAuth = flickr.Auth()


## The following line gets a "frob". The frob will change
## each time you call it, and it needs to be the same
## throughout the authentication process, so once it is
## put into a variable, that variable will be used in future.

frob = myAuth.getFrob()


## The following line generates a link that the user needs
## to be sent to. The user must be logged into Flickr in the
## browser that is opened, and it will ask if it wishes to
## allow your program to access it. Your API KEY must be
## setup correctly within Flickr for this to work. See
## below if you have any problems.
##
## The permissions and frob variable are passed onto
## the link method.

link = myAuth.loginLink(permission,frob)


## The following line just lets the user know they need
## to be logged in, and gives them a chance to before
## the rest of the script is processed.

raw_input("Please make sure you are logged into Flickr in Firefox")


## The following opens the link in Firefox under a Linux installation
## There is a better way, but this way is fine for now.

firefox=os.popen( 'firefox \"' + link + '\"' )


## A firefox window will open asking the user if they wish to allow
## your program/api key to access their account. Once they have
## allowed it, the program can continue, so you need to ask
## the user if they have.

raw_input("A Firefox window should have opened. Press enter when you have authorized this program to access your account")


## A token is needed, which can now be generated with the
## following line of code.

token = myAuth.getToken(frob)


## This token cannot be got again, so the program will
## need to store it somewhere. The following lines
## of code will save it to token.txt in the current
## working directory.

f = file('token.txt','w')
f.write(token)
f.close()

