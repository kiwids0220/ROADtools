import getpass
import sys
import json
import argparse
import base64
import datetime
import uuid
import binascii
import time
import codecs
from urllib.parse import urlparse, parse_qs, quote_plus
from xml.sax.saxutils import escape as xml_escape
import xml.etree.ElementTree as ET
from xml.dom.minidom import parseString
import os
from cryptography.hazmat.primitives import serialization, padding, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.kbkdf import CounterLocation, KBKDFHMAC, Mode
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import requests
import adal
import jwt



WELLKNOWN_RESOURCES = {
    "msgraph": "https://graph.microsoft.com/",
    "aadgraph": "https://graph.windows.net/",
    "devicereg": "urn:ms-drs:enterpriseregistration.windows.net",
    "drs": "urn:ms-drs:enterpriseregistration.windows.net",
    "azrm": "https://management.core.windows.net/",
    "azurerm": "https://management.core.windows.net/",
}

WELLKNOWN_CLIENTS = {
    "aadps": "1b730954-1685-4b74-9bfd-dac224a7b894",
    "azcli": "04b07795-8ddb-461a-bbee-02f9e1bf7b46",
    "teams": "1fec8e78-bce4-4aaf-ab1b-5451cc387264",
    "msteams": "1fec8e78-bce4-4aaf-ab1b-5451cc387264",
    "azps": "1950a258-227b-4e31-a9cf-717495945fc2",
    "msedge": "ecd6b820-32c2-49b6-98a6-444530e5a77a",
    "edge": "ecd6b820-32c2-49b6-98a6-444530e5a77a",
    "msbroker": "29d9ed98-a469-4536-ade2-f981bc1d605e",
    "broker": "29d9ed98-a469-4536-ade2-f981bc1d605e"
}

DSSO_BODY_KERBEROS = '''<?xml version='1.0' encoding='UTF-8'?>
<s:Envelope
    xmlns:s='http://www.w3.org/2003/05/soap-envelope'
    xmlns:wsse='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'
    xmlns:saml='urn:oasis:names:tc:SAML:1.0:assertion'
    xmlns:wsp='http://schemas.xmlsoap.org/ws/2004/09/policy'
    xmlns:wsu='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'
    xmlns:wsa='http://www.w3.org/2005/08/addressing'
    xmlns:wssc='http://schemas.xmlsoap.org/ws/2005/02/sc'
    xmlns:wst='http://schemas.xmlsoap.org/ws/2005/02/trust'>
    <s:Header>
        <wsa:Action s:mustUnderstand='1'>http://schemas.xmlsoap.org/ws/2005/02/trust/RST/Issue</wsa:Action>
        <wsa:To s:mustUnderstand='1'>https://autologon.microsoftazuread-sso.com/{tenant}/winauth/trust/2005/windowstransport?client-request-id=4190b9ab-205d-4024-8caa-aedb3f79988b</wsa:To>
        <wsa:MessageID>urn:uuid:36a2e970-3107-4e3f-99dd-569a9588f02c</wsa:MessageID>
    </s:Header>
    <s:Body>
        <wst:RequestSecurityToken Id='RST0'>
            <wst:RequestType>http://schemas.xmlsoap.org/ws/2005/02/trust/Issue</wst:RequestType>
            <wsp:AppliesTo>
                <wsa:EndpointReference>
                    <wsa:Address>urn:federation:MicrosoftOnline</wsa:Address>
                </wsa:EndpointReference>
            </wsp:AppliesTo>
            <wst:KeyType>http://schemas.xmlsoap.org/ws/2005/05/identity/NoProofKey</wst:KeyType>
        </wst:RequestSecurityToken>
    </s:Body>
</s:Envelope>
'''

DSSO_BODY_USERPASS = '''<?xml version='1.0' encoding='UTF-8'?>
<s:Envelope xmlns:s='http://www.w3.org/2003/05/soap-envelope' xmlns:a='http://www.w3.org/2005/08/addressing' xmlns:u='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd'>
  <s:Header>
    <a:Action s:mustUnderstand='1'>http://schemas.xmlsoap.org/ws/2005/02/trust/RST/Issue</a:Action>
    <a:MessageID>urn:uuid:a5c80716-16fe-473c-bb5d-be0602f9e7fd</a:MessageID>
    <a:ReplyTo>
      <a:Address>http://www.w3.org/2005/08/addressing/anonymous</a:Address>
    </a:ReplyTo>
    <a:To s:mustUnderstand='1'>https://autologon.microsoftazuread-sso.com/{tenant}/winauth/trust/2005/usernamemixed?client-request-id=19ac39db-81d2-4713-8046-b0b7240592be</a:To>
    <o:Security s:mustUnderstand='1' xmlns:o='http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd'>
      <u:Timestamp u:Id='_0'>
        <u:Created>2020-11-23T14:50:44.068Z</u:Created>
        <u:Expires>2020-11-23T15:00:44.068Z</u:Expires>
      </u:Timestamp>
      <o:UsernameToken u:Id='uuid-3e66cabc-66d3-4447-a1c2-ef7ba45274f7'>
        <o:Username>{username}</o:Username>
        <o:Password>{password}</o:Password>
      </o:UsernameToken>
    </o:Security>
  </s:Header>
  <s:Body>
    <trust:RequestSecurityToken xmlns:trust='http://schemas.xmlsoap.org/ws/2005/02/trust'>
      <wsp:AppliesTo xmlns:wsp='http://schemas.xmlsoap.org/ws/2004/09/policy'>
        <a:EndpointReference>
          <a:Address>urn:federation:MicrosoftOnline</a:Address>
        </a:EndpointReference>
      </wsp:AppliesTo>
      <trust:KeyType>http://schemas.xmlsoap.org/ws/2005/05/identity/NoProofKey</trust:KeyType>
      <trust:RequestType>http://schemas.xmlsoap.org/ws/2005/02/trust/Issue</trust:RequestType>
    </trust:RequestSecurityToken>
  </s:Body>
</s:Envelope>
'''

def get_data(data):
    return base64.urlsafe_b64decode(data+('='*(len(data)%4)))

class AuthenticationException(Exception):
    """
    Generic exception we can throw when auth fails so that the error
    goes back to the user.
    """

class Authentication():
    """
    Authentication class for ROADtools
    """
    def __init__(self, username=None, password=None, tenant=None, client_id='1b730954-1685-4b74-9bfd-dac224a7b894'):
        self.username = username
        self.password = password
        self.tenant = tenant
        self.client_id = None
        self.set_client_id(client_id)
        self.resource_uri = 'https://graph.windows.net/'
        self.tokendata = {}
        self.refresh_token = None
        self.saml_token = None
        self.access_token = None
        self.proxies = None
        self.verify = True
        self.outfile = None
        self.debug = False
        self.scope = None

    def get_authority_url(self):
        """
        Returns the authority URL for the tenant specified, or the
        common one if no tenant was specified
        """
        if self.tenant is not None:
            return f'https://login.microsoftonline.com/{self.tenant}'
        return 'https://login.microsoftonline.com/common'

    def set_client_id(self, clid):
        """
        Sets client ID to use (accepts aliases)
        """
        self.client_id = self.lookup_client_id(clid)

    def set_resource_uri(self, uri):
        """
        Sets resource URI to use (accepts aliases)
        """
        self.resource_uri = self.lookup_resource_uri(uri)

    def authenticate_device_code(self):
        """
        Authenticate the end-user using device auth.
        """

        authority_host_uri = self.get_authority_url()

        context = adal.AuthenticationContext(authority_host_uri, api_version=None, proxies=self.proxies, verify_ssl=self.verify)
        code = context.acquire_user_code(self.resource_uri, self.client_id)
        print(code['message'])
        self.tokendata = context.acquire_token_with_device_code(self.resource_uri, code, self.client_id)
        return self.tokendata

    def authenticate_username_password(self):
        """
        Authenticate using user w/ username + password.
        This doesn't work for users or tenants that have multi-factor authentication required.
        """
        authority_uri = self.get_authority_url()
        context = adal.AuthenticationContext(authority_uri, api_version=None, proxies=self.proxies, verify_ssl=self.verify)
        self.tokendata = context.acquire_token_with_username_password(self.resource_uri, self.username, self.password, self.client_id)

        return self.tokendata

    def authenticate_as_app(self):
        """
        Authenticate with an APP id + secret (password credentials assigned to serviceprinicpal)
        """
        authority_uri = self.get_authority_url()

        context = adal.AuthenticationContext(authority_uri, api_version=None, proxies=self.proxies, verify_ssl=self.verify)
        self.tokendata = context.acquire_token_with_client_credentials(self.resource_uri, self.client_id, self.password)
        return self.tokendata

    def authenticate_with_code(self, code, redirurl, client_secret=None):
        """
        Authenticate with a code plus optional secret in case of a non-public app (authorization grant)
        """
        authority_uri = self.get_authority_url()

        context = adal.AuthenticationContext(authority_uri, api_version=None, proxies=self.proxies, verify_ssl=self.verify)
        self.tokendata = context.acquire_token_with_authorization_code(code, redirurl, self.resource_uri, self.client_id, client_secret)
        return self.tokendata

    def authenticate_with_refresh(self, oldtokendata):
        """
        Authenticate with a refresh token, refreshes the refresh token
        and obtains an access token
        """
        authority_uri = self.get_authority_url()

        context = adal.AuthenticationContext(authority_uri, api_version=None, proxies=self.proxies, verify_ssl=self.verify)
        newtokendata = context.acquire_token_with_refresh_token(oldtokendata['refreshToken'], self.client_id, self.resource_uri)
        # Overwrite fields
        for ikey, ivalue in newtokendata.items():
            self.tokendata[ikey] = ivalue
        access_token = newtokendata['accessToken']
        tokens = access_token.split('.')
        inputdata = json.loads(base64.b64decode(tokens[1]+('='*(len(tokens[1])%4))))
        self.tokendata['_clientId'] = self.client_id
        self.tokendata['tenantId'] = inputdata['tid']
        return self.tokendata

    def authenticate_with_refresh_native(self, refresh_token, client_secret=None, additionaldata=None, returnreply=False):
        """
        Authenticate with a refresh token plus optional secret in case of a non-public app (authorization grant)
        Native ROADlib implementation without adal requirement
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "resource": self.resource_uri,
        }
        if client_secret:
            data['client_secret'] = client_secret
        if additionaldata:
            data = {**data, **additionaldata}
        res = requests.post(f"{authority_uri}/oauth2/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        access_token = tokenreply['access_token']
        tokens = access_token.split('.')
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        try:
            inputdata = json.loads(base64.b64decode(tokens[1]+('='*(len(tokens[1])%4))))
            self.tokendata['_clientId'] = self.client_id
            self.tokendata['tenantId'] = inputdata['tid']
        except KeyError:
            pass
        return self.tokendata

    def authenticate_with_refresh_native_v2(self, refresh_token, client_secret=None, additionaldata=None, returnreply=False):
        """
        Authenticate with a refresh token plus optional secret in case of a non-public app (authorization grant)
        Native ROADlib implementation without adal requirement
        This function calls identity platform v2 and thus requires a scope instead of resource
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": self.scope,
        }
        if client_secret:
            data['client_secret'] = client_secret
        if additionaldata:
            data = {**data, **additionaldata}
        res = requests.post(f"{authority_uri}/oauth2/v2.0/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata

    def authenticate_with_code_native(self, code, redirurl, client_secret=None, pkce_secret=None, additionaldata=None, returnreply=False):
        """
        Authenticate with a code plus optional secret in case of a non-public app (authorization grant)
        Native ROADlib implementation without adal requirement - also supports PKCE
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirurl,
            "resource": self.resource_uri,
        }
        if client_secret:
            data['client_secret'] = client_secret
        if additionaldata:
            data = {**data, **additionaldata}
        if pkce_secret:
            raise NotImplementedError
        res = requests.post(f"{authority_uri}/oauth2/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata

    def authenticate_with_code_native_v2(self, code, redirurl, client_secret=None, pkce_secret=None, additionaldata=None, returnreply=False):
        """
        Authenticate with a code plus optional secret in case of a non-public app (authorization grant)
        Native ROADlib implementation without adal requirement - also supports PKCE
        This function calls identity platform v2 and thus requires a scope instead of resource
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirurl,
            "scope": self.scope,
        }
        if client_secret:
            data['client_secret'] = client_secret
        if additionaldata:
            data = {**data, **additionaldata}
        if pkce_secret:
            raise NotImplementedError
        res = requests.post(f"{authority_uri}/oauth2/v2.0/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata

    def authenticate_with_code_encrypted(self, code, sessionkey, redirurl):
        '''
        Encrypted code redemption. Like normal code flow but requires
        session key to decrypt response.
        '''
        authority_uri = self.get_authority_url()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirurl,
            "client_id": self.client_id,
            "client_info":1,
            "windows_api_version":"2.0"
        }
        res = requests.post(f"{authority_uri}/oauth2/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        prtdata = res.text
        data = self.decrypt_auth_response(prtdata, sessionkey, asjson=True)
        return data

    def authenticate_with_saml_native(self, saml_token, additionaldata=None, returnreply=False):
        """
        Authenticate with a SAML token from the Federation Server
        Native ROADlib implementation without adal requirement
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:saml1_1-bearer",
            "assertion": base64.b64encode(saml_token.encode('utf-8')).decode('utf-8'),
            "resource": self.resource_uri,
        }
        if additionaldata:
            data = {**data, **additionaldata}
        res = requests.post(f"{authority_uri}/oauth2/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata

    def authenticate_with_saml_native_v2(self, saml_token, additionaldata=None, returnreply=False):
        """
        Authenticate with a SAML token from the Federation Server
        Native ROADlib implementation without adal requirement
        This function calls identity platform v2 and thus requires a scope instead of resource
        """
        authority_uri = self.get_authority_url()
        data = {
            "client_id": self.client_id,
            "grant_type": "urn:ietf:params:oauth:grant-type:saml1_1-bearer",
            "assertion": base64.b64encode(saml_token.encode('utf-8')).decode('utf-8'),
            "scope": self.scope,
        }
        if additionaldata:
            data = {**data, **additionaldata}
        res = requests.post(f"{authority_uri}/oauth2/v2.0/token", data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata

    def get_desktopsso_token(self, username=None, password=None, krbtoken=None):
        '''
        Get desktop SSO token either with plain username and password, or with a Kerberos auth token
        '''
        if username and password:
            rbody = DSSO_BODY_USERPASS.format(username=xml_escape(username), password=xml_escape(password), tenant=self.tenant)
            headers = {
                'Content-Type':'application/soap+xml; charset=utf-8',
                'SOAPAction': 'http://schemas.xmlsoap.org/ws/2005/02/trust/RST/Issue',
            }
            res = requests.post(f'https://autologon.microsoftazuread-sso.com/{self.tenant}/winauth/trust/2005/usernamemixed?client-request-id=19ac39db-81d2-4713-8046-b0b7240592be', headers=headers, data=rbody, proxies=self.proxies, verify=self.verify)
            tree = ET.fromstring(res.content)
            els = tree.findall('.//DesktopSsoToken')
            if len(els) > 0:
                token = els[0].text
                return token
            else:
                # Try finding error
                elres = tree.iter('{http://schemas.microsoft.com/Passport/SoapServices/SOAPFault}text')
                if elres:
                    errtext = next(elres)
                    raise AuthenticationException(errtext.text)
                else:
                    raise AuthenticationException(parseString(res.content).toprettyxml(indent='  '))
        elif krbtoken:
            rbody = DSSO_BODY_KERBEROS.format(tenant=self.tenant)
            headers = {
                'Content-Type':'application/soap+xml; charset=utf-8',
                'SOAPAction': 'http://schemas.xmlsoap.org/ws/2005/02/trust/RST/Issue',
                'Authorization': f'Negotiate {krbtoken}'
            }
            res = requests.post(f'https://autologon.microsoftazuread-sso.com/{self.tenant}/winauth/trust/2005/windowstransport?client-request-id=19ac39db-81d2-4713-8046-b0b7240592be', headers=headers, data=rbody, proxies=self.proxies, verify=self.verify)
            tree = ET.fromstring(res.content)
            els = tree.findall('.//DesktopSsoToken')
            if len(els) > 0:
                token = els[0].text
                return token
            else:
                print(parseString(res.content).toprettyxml(indent='  '))
                return False
        else:
            return False

    def authenticate_with_desktopsso_token(self, dssotoken, returnreply=False, additionaldata=None):
        '''
        Authenticate with Desktop SSO token
        '''
        headers = {
            'x-client-SKU': 'PCL.Desktop',
            'x-client-Ver': '3.19.7.16602',
            'x-client-CPU': 'x64',
            'x-client-OS': 'Microsoft Windows NT 10.0.18363.0',
            'x-ms-PKeyAuth': '1.0',
            'client-request-id': '19ac39db-81d2-4713-8046-b0b7240592be',
            'return-client-request-id': 'true',
        }
        claim = base64.b64encode('<saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:1.0:assertion"><DesktopSsoToken>{0}</DesktopSsoToken></saml:Assertion>'.format(dssotoken).encode('utf-8')).decode('utf-8')
        data = {
            'resource': self.resource_uri,
            'client_id': self.client_id,
            'grant_type': 'urn:ietf:params:oauth:grant-type:saml1_1-bearer',
            'assertion': claim,
        }
        authority_uri = self.get_authority_url()
        if additionaldata:
            data = {**data, **additionaldata}
        res = requests.post(f"{authority_uri}/oauth2/token", headers=headers, data=data, proxies=self.proxies, verify=self.verify)
        if res.status_code != 200:
            raise AuthenticationException(res.text)
        tokenreply = res.json()
        if returnreply:
            return tokenreply
        self.tokendata = self.tokenreply_to_tokendata(tokenreply)
        return self.tokendata


    def build_auth_url(self, redirurl, response_type, scope=None, state=None):
        '''
        Build authorize URL. Can be v2 by specifying scope, otherwise defaults
        to v1 with resource
        '''
        urlt_v2 = 'https://login.microsoftonline.com/{3}/oauth2/v2.0/authorize?response_type={4}&client_id={0}&scope={2}&redirect_uri={1}&state={5}'
        urlt_v1 = 'https://login.microsoftonline.com/{3}/oauth2/authorize?response_type={4}&client_id={0}&resource={2}&redirect_uri={1}&state={5}'
        if not state:
            state = str(uuid.uuid4())
        if not self.tenant:
            tenant = 'common'
        else:
            tenant = self.tenant
        if scope:
            # v2
            return urlt_v2.format(
                quote_plus(self.client_id),
                quote_plus(redirurl),
                quote_plus(scope),
                quote_plus(tenant),
                quote_plus(response_type),
                quote_plus(state)
            )
        # Else default to v1 identity endpoint
        return urlt_v1.format(
            quote_plus(self.client_id),
            quote_plus(redirurl),
            quote_plus(self.resource_uri),
            quote_plus(tenant),
            quote_plus(response_type),
            quote_plus(state)
        )

    def create_prt_cookie_kdf_ver_2(self, prt, sessionkey, nonce=None):
        """
        KDF version 2 cookie construction
        """
        context = os.urandom(24)
        headers = {
            'ctx': base64.b64encode(context).decode('utf-8'), #.rstrip('=')
            'kdf_ver': 2
        }
        # Nonce should be requested by calling function, otherwise
        # old time based model is used
        if nonce:
            payload = {
                "refresh_token": prt,
                "is_primary": "true",
                "request_nonce": nonce
            }
        else:
            payload = {
                "refresh_token": prt,
                "is_primary": "true",
                "iat": str(int(time.time()))
            }
        # Sign with random key just to get jwt body in right encoding
        tempjwt = jwt.encode(payload, os.urandom(32), algorithm='HS256', headers=headers)
        jbody = tempjwt.split('.')[1]
        jwtbody = base64.b64decode(jbody+('='*(len(jbody)%4)))

        # Now calculate the derived key based on random context plus jwt body
        _, derived_key = self.calculate_derived_key_v2(sessionkey, context, jwtbody)
        cookie = jwt.encode(payload, derived_key, algorithm='HS256', headers=headers)
        return cookie

    def authenticate_with_prt_v2(self, prt, sessionkey):
        """
        KDF version 2 PRT auth
        """
        nonce = self.get_prt_cookie_nonce()
        if not nonce:
            return False

        cookie = self.create_prt_cookie_kdf_ver_2(prt, sessionkey, nonce)
        return self.authenticate_with_prt_cookie(cookie)

    def authenticate_with_prt(self, prt, context, derived_key=None, sessionkey=None):
        """
        Authenticate with a PRT and given context/derived key
        Uses KDF version 1 (legacy)
        """
        # If raw key specified, use that
        if not derived_key and sessionkey:
            context, derived_key = self.calculate_derived_key(sessionkey, context)

        headers = {
            'ctx': base64.b64encode(context).decode('utf-8'),
        }
        nonce = self.get_prt_cookie_nonce()
        if not nonce:
            return False
        payload = {
            "refresh_token": prt,
            "is_primary": "true",
            "request_nonce": nonce
        }
        cookie = jwt.encode(payload, derived_key, algorithm='HS256', headers=headers)
        return self.authenticate_with_prt_cookie(cookie)

    def calculate_derived_key_v2(self, sessionkey, context, jwtbody):
        """
        Derived key calculation v2, which uses the JWT body
        """
        digest = hashes.Hash(hashes.SHA256())
        digest.update(context)
        digest.update(jwtbody)
        kdfcontext = digest.finalize()
        # From here on identical to v1
        return self.calculate_derived_key(sessionkey, kdfcontext)

    def calculate_derived_key(self, sessionkey, context=None):
        """
        Calculate the derived key given a session key and optional context using KBKDFHMAC
        """
        label = b"AzureAD-SecureConversation"
        if not context:
            context = os.urandom(24)
        backend = default_backend()
        kdf = KBKDFHMAC(
            algorithm=hashes.SHA256(),
            mode=Mode.CounterMode,
            length=32,
            rlen=4,
            llen=4,
            location=CounterLocation.BeforeFixed,
            label=label,
            context=context,
            fixed=None,
            backend=backend
        )
        derived_key = kdf.derive(sessionkey)
        return context, derived_key

    def decrypt_auth_response(self, responsedata, sessionkey, asjson=False):
        """
        Decrypt an encrypted authentication response, which is a JWE
        encrypted using the sessionkey
        """
        if responsedata[:2] == '{"':
            # This doesn't appear encrypted
            if asjson:
                return json.loads(responsedata)
            return responsedata
        dataparts = responsedata.split('.')

        headers = json.loads(get_data(dataparts[0]))
        _, derived_key = self.calculate_derived_key(sessionkey, base64.b64decode(headers['ctx']))
        data = dataparts[3]
        iv = dataparts[2]
        authtag = dataparts[4]
        if len(get_data(iv)) == 12:
            # This appears to be actual AES GCM
            aesgcm = AESGCM(derived_key)
            # JWE header is used as additional data
            # Totally legit source: https://github.com/AzureAD/microsoft-authentication-library-common-for-objc/compare/dev...kedicl/swift/addframework#diff-ec15357c1b0dba2f2304f64750e5126ec910156f09c0f75eba0bb22cb83ada6dR46
            # Also hinted at in RFC examples https://www.rfc-editor.org/rfc/rfc7516.txt
            depadded_data = aesgcm.decrypt(get_data(iv), get_data(data) + get_data(authtag), dataparts[0].encode('utf-8'))
        else:
            cipher = Cipher(algorithms.AES(derived_key), modes.CBC(get_data(iv)))
            decryptor = cipher.decryptor()
            decrypted_data = decryptor.update(get_data(data)) + decryptor.finalize()
            unpadder = padding.PKCS7(128).unpadder()
            depadded_data = unpadder.update(decrypted_data) + unpadder.finalize()
        if asjson:
            jdata = json.loads(depadded_data)
            return jdata
        else:
            return depadded_data

    def get_srv_challenge(self):
        """
        Request server challenge (nonce) to use with a PRT
        """
        data = {'grant_type':'srv_challenge'}
        res = requests.post('https://login.microsoftonline.com/common/oauth2/token', data=data, proxies=self.proxies, verify=self.verify)
        return res.json()

    def get_prt_cookie_nonce(self):
        """
        Request a nonce to sign in with. This nonce is taken from the sign-in page, which
        is how Chrome processes it, but it could probably also be obtained using the much
        simpler request from the get_srv_challenge function.
        """
        ses = requests.session()
        ses.proxies = self.proxies
        ses.verify = self.verify
        params = {
            'resource': self.resource_uri,
            'client_id': self.client_id,
            'response_type': 'code',
            'haschrome': '1',
            'redirect_uri': 'https://login.microsoftonline.com/common/oauth2/nativeclient',
            'client-request-id': str(uuid.uuid4()),
            'x-client-SKU': 'PCL.Desktop',
            'x-client-Ver': '3.19.7.16602',
            'x-client-CPU': 'x64',
            'x-client-OS': 'Microsoft Windows NT 10.0.19569.0',
            'site_id': 501358,
            'mscrid': str(uuid.uuid4())
        }
        headers = {
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 10.0; Win64; x64; Trident/7.0; .NET4.0C; .NET4.0E)',
            'UA-CPU': 'AMD64',
        }
        res = ses.get('https://login.microsoftonline.com/Common/oauth2/authorize', params=params, headers=headers, allow_redirects=False)
        if self.debug:
            with open('roadtools.debug.html','w') as outfile:
                outfile.write(str(res.headers))
                outfile.write('------\n\n\n-----')
                outfile.write(res.content.decode('utf-8'))
        if res.status_code == 302 and res.headers['Location']:
            ups = urlparse(res.headers['Location'])
            qdata = parse_qs(ups.query)
            if not 'sso_nonce' in qdata:
                print('No nonce found in redirect!')
                return
            return qdata['sso_nonce'][0]
        else:
            # Try to find SSO nonce in json config
            startpos = res.content.find(b'$Config=')
            stoppos = res.content.find(b'//]]></script>')
            if startpos == -1 or stoppos == -1:
                print('No redirect or nonce config was returned!')
                return
            else:
                jsonbytes = res.content[startpos+8:stoppos-2]
                try:
                    jdata = json.loads(jsonbytes)
                except json.decoder.JSONDecodeError:
                    print('Failed to parse config JSON')
                try:
                    nonce = jdata['bsso']['nonce']
                except KeyError:
                    print('No nonce found in browser config')
                    return
                return nonce


    def authenticate_with_prt_cookie(self, cookie, context=None, derived_key=None, verify_only=False, sessionkey=None, redirurl=None, return_code=False):
        """
        Authenticate with a PRT cookie, optionally re-signing the cookie if a key is given
        """
        # Load cookie
        jdata = jwt.decode(cookie, options={"verify_signature":False}, algorithms=['HS256'])
        # Does it have a nonce?
        if not 'request_nonce' in jdata:
            nonce = self.get_prt_cookie_nonce()
            if not nonce:
                return False
            print('Requested nonce from server to use with ROADtoken: %s' % nonce)
            if not derived_key and not sessionkey:
                return False
        else:
            nonce = jdata['request_nonce']

        # If raw key specified, use that
        if not derived_key and sessionkey:
            context, derived_key = self.calculate_derived_key(sessionkey, context)

        # If a derived key was specified, we use that
        if derived_key:
            sdata = derived_key
            headers = jwt.get_unverified_header(cookie)
            if context is None or verify_only:
                # Verify JWT
                try:
                    jdata = jwt.decode(cookie, sdata, algorithms=['HS256'])
                except jwt.exceptions.InvalidSignatureError:
                    print('Signature invalid with given derived key')
                    return False
                if verify_only:
                    print('PRT verified with given derived key!')
                    return False
            else:
                # Don't verify JWT, just load it
                jdata = jwt.decode(cookie, sdata, options={"verify_signature":False}, algorithms=['HS256'])
            # Since a derived key was specified, we get a new nonce
            nonce = self.get_prt_cookie_nonce()
            jdata['request_nonce'] = nonce
            if context:
                # Resign with custom context, should be in base64
                newheaders = {
                    'ctx': base64.b64encode(context).decode('utf-8') #.rstrip('=')
                }
                cookie = jwt.encode(jdata, sdata, algorithm='HS256', headers=newheaders)
                print('Re-signed PRT cookie using custom context')
            else:
                newheaders = {
                    'ctx': headers['ctx']
                }
                cookie = jwt.encode(jdata, sdata, algorithm='HS256', headers=newheaders)
                print('Re-signed PRT cookie using derived key')

        ses = requests.session()
        ses.proxies = self.proxies
        ses.verify = self.verify
        authority_uri = self.get_authority_url()
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'haschrome': '1',
            'redirect_uri': 'https://login.microsoftonline.com/common/oauth2/nativeclient',
            'client-request-id': str(uuid.uuid4()),
            'x-client-SKU': 'PCL.Desktop',
            'x-client-Ver': '3.19.7.16602',
            'x-client-CPU': 'x64',
            'x-client-OS': 'Microsoft Windows NT 10.0.19569.0',
            'site_id': 501358,
            'sso_nonce': nonce,
            'mscrid': str(uuid.uuid4())
        }
        if self.scope:
            # Switch to identity platform v2 endpoint
            params['scope'] = self.scope
            url = f'{authority_uri}/oauth2/v2.0/authorize'
            coderedeemfunc = self.authenticate_with_code_native_v2
        else:
            params['resource'] = self.resource_uri
            url = f'{authority_uri}/oauth2/authorize'
            coderedeemfunc = self.authenticate_with_code_native

        headers = {
            'User-Agent': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 10.0; Win64; x64; Trident/7.0; .NET4.0C; .NET4.0E)',
            'UA-CPU': 'AMD64',
        }
        cookies = {
            'x-ms-RefreshTokenCredential': cookie
        }
        if redirurl:
            params['redirect_uri'] = redirurl

        res = ses.get(url, params=params, headers=headers, cookies=cookies, allow_redirects=False)
        if res.status_code == 302 and params['redirect_uri'].lower() in res.headers['Location'].lower():
            ups = urlparse(res.headers['Location'])
            qdata = parse_qs(ups.query)
            # Return code if requested, otherwise redeem it
            if return_code:
                return qdata['code'][0]
            return coderedeemfunc(qdata['code'][0], params['redirect_uri'])
        if res.status_code == 302 and 'sso_nonce' in res.headers['Location'].lower():
            ups = urlparse(res.headers['Location'])
            qdata = parse_qs(ups.query)
            if 'sso_nonce' in qdata:
                nonce = qdata['sso_nonce'][0]
                print(f'Redirected with new nonce. Old nonce may be expired. New nonce: {nonce}')
        if self.debug:
            with open('roadtools.debug.html','w') as outfile:
                outfile.write(str(res.headers))
                outfile.write('------\n\n\n-----')
                outfile.write(res.content.decode('utf-8'))

        # Try to find SSO nonce in json config
        startpos = res.content.find(b'$Config=')
        stoppos = res.content.find(b'//]]></script>')
        if startpos != -1 and stoppos != -1:
            jsonbytes = res.content[startpos+8:stoppos-2]
            try:
                jdata = json.loads(jsonbytes)
                try:
                    error = jdata['strMainMessage']
                    print(f'Error from STS: {error}')
                    error = jdata['strAdditionalMessage']
                    print(f'Additional info: {error}')
                    error = jdata['strServiceExceptionMessage']
                    print(f'Exception: {error}')
                except KeyError:
                    pass
            except json.decoder.JSONDecodeError:
                pass
        print('No authentication code was returned, make sure the PRT cookie is valid')
        print('It is also possible that the sign-in was blocked by Conditional Access policies')
        return False

    @staticmethod
    def get_sub_argparse(auth_parser, for_rr=False):
        """
        Get an argparse subparser for authentication
        """
        auth_parser.add_argument('-u',
                                 '--username',
                                 action='store',
                                 help='Username for authentication')
        auth_parser.add_argument('-p',
                                 '--password',
                                 action='store',
                                 help='Password (leave empty to prompt)')
        auth_parser.add_argument('-t',
                                 '--tenant',
                                 action='store',
                                 help='Tenant ID to auth to (leave blank for default tenant for account)')
        if for_rr:
            helptext = 'Client ID to use when authenticating. (Must be a public client from Microsoft with user_impersonation permissions!). Default: Azure AD PowerShell module App ID'
        else:
            helptext = 'Client ID to use when authenticating. (Must have the required OAuth2 permissions or Application Role for what you want to achieve)'
        auth_parser.add_argument('-c',
                                 '--client',
                                 action='store',
                                 help=helptext,
                                 default='1b730954-1685-4b74-9bfd-dac224a7b894')
        auth_parser.add_argument('-r',
                                 '--resource',
                                 action='store',
                                 help='Resource to authenticate to (Default: https://graph.windows.net)',
                                 default='https://graph.windows.net')
        auth_parser.add_argument('-s',
                                 '--scope',
                                 action='store',
                                 help='Scope to request when authenticating. Not supported in all flows yet. Overrides resource if specified')
        auth_parser.add_argument('--as-app',
                                 action='store_true',
                                 help='Authenticate as App (requires password and client ID set)')
        auth_parser.add_argument('--device-code',
                                 action='store_true',
                                 help='Authenticate using a device code')
        auth_parser.add_argument('--access-token',
                                 action='store',
                                 help='Access token (JWT)')
        auth_parser.add_argument('--refresh-token',
                                 action='store',
                                 help='Refresh token')
        auth_parser.add_argument('--saml-token',
                                 action='store',
                                 help='SAML token from Federation Server')
        auth_parser.add_argument('--prt-cookie',
                                 action='store',
                                 help='Primary Refresh Token cookie from ROADtoken (JWT)')
        auth_parser.add_argument('--prt-init',
                                 action='store_true',
                                 help='Initialize Primary Refresh Token authentication flow (get nonce)')
        auth_parser.add_argument('--prt',
                                 action='store',
                                 help='Primary Refresh Token')
        auth_parser.add_argument('--derived-key',
                                 action='store',
                                 help='Derived key used to re-sign the PRT cookie (as hex key)')
        auth_parser.add_argument('--prt-context',
                                 action='store',
                                 help='Primary Refresh Token context for the derived key (as hex key)')
        auth_parser.add_argument('--prt-sessionkey',
                                 action='store',
                                 help='Primary Refresh Token session key (as hex key)')
        auth_parser.add_argument('--prt-verify',
                                 action='store_true',
                                 help='Verify the Primary Refresh Token and exit')
        auth_parser.add_argument('--kdf-v1',
                                 action='store_true',
                                 help='Use the older KDF version for PRT auth, may not work with PRTs from modern OSs')
        auth_parser.add_argument('-f',
                                 '--tokenfile',
                                 action='store',
                                 help='File to store the credentials (default: .roadtools_auth)',
                                 default='.roadtools_auth')
        auth_parser.add_argument('--tokens-stdout',
                                 action='store_true',
                                 help='Do not store tokens on disk, pipe to stdout instead')
        auth_parser.add_argument('--debug',
                                 action='store_true',
                                 help='Enable debug logging to disk')
        return auth_parser

    @staticmethod
    def ensure_binary_derivedkey(derived_key):
        if not derived_key:
            return None
        secret = derived_key.replace(' ','')
        sdata = binascii.unhexlify(secret)
        return sdata

    @staticmethod
    def ensure_binary_sessionkey(sessionkey):
        if not sessionkey:
            return None
        if len(sessionkey) == 44:
            keybytes = base64.b64decode(sessionkey)
        else:
            sessionkey = sessionkey.replace(' ','')
            keybytes = binascii.unhexlify(sessionkey)
        return keybytes

    @staticmethod
    def ensure_binary_context(context):
        if not context:
            return None
        return binascii.unhexlify(context)

    @staticmethod
    def ensure_plain_prt(prt):
        if not prt:
            return None
        # May be base64 encoded
        if not '.' in prt:
            prt = base64.b64decode(prt+('='*(len(prt)%4))).decode('utf-8')
        return prt

    @staticmethod
    def parse_accesstoken(token):
        tokenparts = token.split('.')
        tokendata = json.loads(get_data(tokenparts[1]))
        tokenobject = {
            'accessToken': token,
            'tokenType': 'Bearer',
            'expiresOn': datetime.datetime.fromtimestamp(tokendata['exp']).strftime('%Y-%m-%d %H:%M:%S'),
            'tenantId': tokendata['tid'],
            '_clientId': tokendata['appid']
        }
        return tokenobject, tokendata

    @staticmethod
    def tokenreply_to_tokendata(tokenreply, client_id=None):
        """
        Convert /token reply from Azure to ADAL compatible object
        """
        tokenobject = {
            'tokenType': tokenreply['token_type'],
        }
        try:
            tokenobject['expiresOn'] = datetime.datetime.fromtimestamp(int(tokenreply['expires_on'])).strftime('%Y-%m-%d %H:%M:%S')
        except KeyError:
            tokenobject['expiresOn'] = (datetime.datetime.now() + datetime.timedelta(seconds=int(tokenreply['expires_in']))).strftime('%Y-%m-%d %H:%M:%S')

        tokenparts = tokenreply['access_token'].split('.')
        inputdata = json.loads(base64.b64decode(tokenparts[1]+('='*(len(tokenparts[1])%4))))
        try:
            tokenobject['tenantId'] = inputdata['tid']
        except KeyError:
            pass
        if client_id:
            tokenobject['_clientId'] = client_id
        else:
            try:
                tokenobject['_clientId'] = inputdata['appid']
            except KeyError:
                pass
        translate_map = {
            'access_token': 'accessToken',
            'refresh_token': 'refreshToken',
            'id_token': 'idToken',
            'token_type': 'tokenType'
        }
        for newname, oldname in translate_map.items():
            if newname in tokenreply:
                tokenobject[oldname] = tokenreply[newname]
        return tokenobject

    @staticmethod
    def parse_compact_jwe(jwe, verbose=False, decode_header=True):
        """
        Parse compact JWE according to
        https://datatracker.ietf.org/doc/html/rfc7516#section-3.1
        """
        dataparts = jwe.split('.')
        header, enc_key, iv, ciphertext, auth_tag = dataparts
        parsed_header = json.loads(get_data(header))
        if verbose:
            print("Header (decoded):")
            print(json.dumps(parsed_header, sort_keys=True, indent=4))
            print("Encrypted key:")
            print(enc_key)
            print('IV:')
            print(iv)
            print("Ciphertext:")
            print(ciphertext)
            print("Auth tag:")
            print(auth_tag)
        if decode_header:
            return parsed_header, enc_key, iv, ciphertext, auth_tag
        return header, enc_key, iv, ciphertext, auth_tag

    @staticmethod
    def parse_jwt(jwtoken):
        """
        Simple JWT parsing function
        returns header and body as dict and signature as bytes
        """
        dataparts = jwtoken.split('.')
        header = json.loads(get_data(dataparts[0]))
        body = json.loads(get_data(dataparts[1]))
        signature = get_data(dataparts[2])
        return header, body, signature

    @staticmethod
    def lookup_resource_uri(uri):
        """
        Translate resource URI aliases
        """
        try:
            resolved = WELLKNOWN_RESOURCES[uri.lower()]
            return resolved
        except KeyError:
            return uri

    @staticmethod
    def lookup_client_id(clid):
        """
        Translate client ID aliases
        """
        try:
            resolved = WELLKNOWN_CLIENTS[clid.lower()]
            return resolved
        except KeyError:
            return clid

    def parse_args(self, args):
        self.username = args.username
        self.password = args.password
        self.tenant = args.tenant
        self.set_client_id(args.client)
        self.access_token = args.access_token
        self.refresh_token = args.refresh_token
        self.saml_token = args.saml_token
        self.outfile = args.tokenfile
        self.debug = args.debug
        self.set_resource_uri(args.resource)
        self.scope = args.scope

        if not self.username is None and self.password is None:
            self.password = getpass.getpass()

    def get_tokens(self, args):
        """
        Get tokens based on the arguments specified.
        Expects args to be generated from get_sub_argparse
        """
        try:
            if self.tokendata:
                return self.tokendata
            if self.refresh_token and not self.access_token:
                if self.refresh_token == 'file':
                    with codecs.open(args.tokenfile, 'r', 'utf-8') as infile:
                        token_data = json.load(infile)
                else:
                    token_data = {'refreshToken': self.refresh_token}
                return self.authenticate_with_refresh_native(token_data['refreshToken'], client_secret=self.password)
            if self.access_token and not self.refresh_token:
                self.tokendata, _ = self.parse_accesstoken(self.access_token)
                return self.tokendata
            if self.username and self.password:
                return self.authenticate_username_password()
            if self.saml_token:
                if self.saml_token.lower() == 'stdin':
                    samltoken = sys.stdin.read()
                else:
                    samltoken = self.saml_token
                if self.scope:
                    # Use v2 endpoint if we have a scope
                    return self.authenticate_with_saml_native_v2(samltoken)
                else:
                    return self.authenticate_with_saml_native(samltoken)
            if args.as_app and self.password:
                return self.authenticate_as_app()
            if args.device_code:
                return self.authenticate_device_code()
            if args.prt_init:
                nonce = self.get_prt_cookie_nonce()
                if nonce:
                    print(f'Requested nonce from server to use with ROADtoken: {nonce}')
                return False
            if args.prt_cookie:
                derived_key = self.ensure_binary_derivedkey(args.derived_key)
                context = self.ensure_binary_context(args.prt_context)
                sessionkey = self.ensure_binary_sessionkey(args.prt_sessionkey)
                return self.authenticate_with_prt_cookie(args.prt_cookie, context, derived_key, args.prt_verify, sessionkey)
            if args.prt and args.prt_context and args.derived_key:
                derived_key = self.ensure_binary_derivedkey(args.derived_key)
                context = self.ensure_binary_context(args.prt_context)
                prt = self.ensure_plain_prt(args.prt)
                return self.authenticate_with_prt(prt, context, derived_key=derived_key)
            if args.prt and args.prt_sessionkey:
                prt = self.ensure_plain_prt(args.prt)
                sessionkey = self.ensure_binary_sessionkey(args.prt_sessionkey)
                if args.kdf_v1:
                    return self.authenticate_with_prt(prt, None, sessionkey=sessionkey)
                else:
                    return self.authenticate_with_prt_v2(prt, sessionkey)

        except adal.adal_error.AdalError as ex:
            print(ex.error_response['error_description'])
            sys.exit(1)

        # If we are here, no auth to try
        print('Not enough information was supplied to authenticate')
        return False

    def save_tokens(self, args):
        if args.tokens_stdout:
            sys.stdout.write(json.dumps(self.tokendata))
        else:
            with codecs.open(self.outfile, 'w', 'utf-8') as outfile:
                json.dump(self.tokendata, outfile)
            print('Tokens were written to {}'.format(self.outfile))

def main():
    parser = argparse.ArgumentParser(add_help=True, description='ROADtools Authentication utility', formatter_class=argparse.RawDescriptionHelpFormatter)
    auth = Authentication()
    auth.get_sub_argparse(parser)
    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)
    args = parser.parse_args()
    auth.parse_args(args)
    if not auth.get_tokens(args):
        return
    auth.save_tokens(args)

if __name__ == '__main__':
    main()
