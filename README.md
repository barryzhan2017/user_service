# user_service
It's a microservice for users's CRUD, JWT authorization, email registration via SNS and SES, 
OAuth2 via Google Cloud and address verification via SmartyStreets.com.



Additional features like JWT authentication and registration via email confirmation is complete.
* JWT can also encrypt our user information for further authorization 
* Email Confirmation is done via by sending AWS SNS when registering new user and
a lambda1 receiving the SNS message will send email using AWS SES. Once a user click
the link which invokes another lambda2, the lambda will update user status by sending 
request to this service. Main problems I met:
  * Use Lambda Proxy integration in Integration Request tab to allow API gateway to send 
    query string to our lambda2
  * Layer should be added by uploading zip file to import external modules for a lambda function
  * Requests module requires additional modules, like chardet, certifi and idna module
  * Permission to publish sns should be added to elastic beanstalk role 
    (although local can access sns).
  * We need request removal from sandbox of our sns account to send emails to unlimited address.
  Under sending statistics, click edit account details to achieve that.
    

