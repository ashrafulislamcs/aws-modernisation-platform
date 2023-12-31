﻿import boto3
import base64
from botocore.exceptions import ClientError
import json

athena_client = boto3.client('athena', region_name='eu-west-2')
sts_client = boto3.client('sts')
ssm_client = boto3.client('ssm', region_name='eu-west-2')
query_location='s3://athena-cloudtrail-query'
athena_db="mod_cloudtrail_logs"
athena_table="cloudtrail_logs"

#Get account numbers from modernsation platform account
def get_accounts():

        # Get environment management secret ARN
        parameter_name = "environment_management_arn"
    
        try:
            get_parameter_response = ssm_client.get_parameter (
                Name=parameter_name,
                WithDecryption=True
            )
            secret_arn=get_parameter_response['Parameter']['Value']

        except ClientError as e:
            print("Unexpected error: %s" % e)
        
        # get account numbers from environment management secret
        region_name = "eu-west-2"
        
        client = boto3.client(
            service_name='secretsmanager',
            region_name=region_name,
        )
        
        try:
            get_secret_value_response = client.get_secret_value(
                    SecretId=secret_arn
            )
            res=json.loads(json.dumps(get_secret_value_response, default=str))
            
            return res
        except ClientError as e:
            if e.response['Error']['Code'] == 'DecryptionFailureException':
                # Secrets Manager can't decrypt the protected secret text using the provided KMS key.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InternalServiceErrorException':
                # An error occurred on the server side.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InvalidParameterException':
                # You provided an invalid value for a parameter.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'InvalidRequestException':
                # You provided a parameter value that is not valid for the current state of the resource.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
            elif e.response['Error']['Code'] == 'ResourceNotFoundException':
                # We can't find the resource that you asked for.
                # Deal with the exception here, and/or rethrow at your discretion.
                raise e
        else:
            # Decrypts secret using the associated KMS CMK.
            # Depending on whether the secret is a string or binary, one of these fields will be populated.
            if 'SecretString' in get_secret_value_response:
                secret = get_secret_value_response['SecretString']
                #res = json.loads(json.dumps(secret, default=str))
                return secret
            else:
                decoded_binary_secret = base64.b64decode(get_secret_value_response['SecretBinary'])
                #res = json.loads(json.dumps(decoded_binary_secret, default=str))
                return decoded_binary_secret
                
#Create AWS Athena database
def create_athena_database():
    
    print("[+] Creating Athena database " + athena_db)
    
    try:
        response = athena_client.start_query_execution(
           
        QueryString='CREATE DATABASE IF NOT EXISTS %s' % athena_db,
        
        ResultConfiguration={'OutputLocation': query_location})
        
    except ClientError as e:
        print("Unexpected error: %s" % e)     

#Drop Athena table 
def drop_athena_table():
    
    print("[+] Dropping Athena table " + athena_table)
    
    try:
        response = athena_client.start_query_execution(
           
        QueryString='DROP TABLE %s'  % athena_table,
        
         QueryExecutionContext={
                'Database': athena_db
         },
         
        ResultConfiguration={'OutputLocation': query_location})
        
    except ClientError as e:
        
        print("[!] Could not drop Athena table")
        print("Unexpected error: %s" % e)     
        
#Create Athena table and add updated AWS accounts to Athena partition  
def create_athena_table(list_accounts):

    print("[+] Updating Athena table " + athena_table)
    
    print("[+] Adding Mod accounts to Athena query: ")
    print(list_accounts)
        
    query = """
            CREATE EXTERNAL TABLE cloudtrail_logs(
                eventVersion STRING,
                userIdentity STRUCT<
                    type: STRING,
                    principalId: STRING,
                    arn: STRING,
                    accountId: STRING,
                    invokedBy: STRING,
                    accessKeyId: STRING,
                    userName: STRING,
                    sessionContext: STRUCT<
                        attributes: STRUCT<
                            mfaAuthenticated: STRING,
                            creationDate: STRING>,
                        sessionIssuer: STRUCT<
                            type: STRING,
                            principalId: STRING,
                            arn: STRING,
                            accountId: STRING,
                            userName: STRING>>>,
                eventTime STRING,
                eventSource STRING,
                eventName STRING,
                awsRegion STRING,
                sourceIpAddress STRING,
                userAgent STRING,
                errorCode STRING,
                errorMessage STRING,
                requestParameters STRING,
                responseElements STRING,
                additionalEventData STRING,
                requestId STRING,
                eventId STRING,
                readOnly STRING,
                resources ARRAY<STRUCT<
                    arn: STRING,
                    accountId: STRING,
                    type: STRING>>,
                eventType STRING,
                apiVersion STRING,
                recipientAccountId STRING,
                serviceEventDetails STRING,
                sharedEventID STRING,
                vpcEndpointId STRING
              )
            PARTITIONED BY (
               `account` string, `region` string, `timestamp` string)
            ROW FORMAT SERDE 'com.amazon.emr.hive.serde.CloudTrailSerde'
            STORED AS INPUTFORMAT 'com.amazon.emr.cloudtrail.CloudTrailInputFormat'
            OUTPUTFORMAT 'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
            LOCATION
              's3://modernisation-platform-logs-cloudtrail/AWSLogs'
            TBLPROPERTIES (
              'projection.enabled'='true',
              'projection.account.type' = 'enum',
              'projection.account.values' = '%s',
              'projection.region.type' = 'enum',
              'projection.region.values' = 'eu-west-1, eu-west-2',
              'projection.timestamp.format'='yyyy/MM/dd',
              'projection.timestamp.interval'='1',
              'projection.timestamp.interval.unit'='DAYS',
              'projection.timestamp.range'='2020/01/01,NOW',
              'projection.timestamp.type'='date',
              'storage.location.template'='s3://modernisation-platform-logs-cloudtrail/AWSLogs/${account}/CloudTrail/${region}/${timestamp}')
      """ % list_accounts
    try:
        response = athena_client.start_query_execution(
            QueryString=query,
            
            QueryExecutionContext={
                'Database': athena_db
         },
            ResultConfiguration={
                'OutputLocation': query_location,
            }
        )
        print(response)
        return response
    
    except ClientError as e:
        print("[-] Could not create Athena table") 
        print("Unexpected error: %s" % e)     
    
 

def lambda_handler(event, context):
    
    try:
        #Get list of accounts 
        list_accounts = []
        
        account = get_accounts()
        
        data_object = json.loads(account['SecretString'])
        data_json =  json.dumps(data_object['account_ids'])
        
        #Get AWS account values and add them to a list
        for key, value in json.loads(data_json).items():
            list_accounts.append(value)
        
        #create athena database if it doesn't exist
        create_athena_database()
        
        drop_athena_table()
        
        #Update Athena table and pass AWS account list as a parameter 
        create_athena_table(','.join(map(str, list_accounts)))
    
    except ClientError as e:
        print("Unexpected error: %s" % e)     
