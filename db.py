import boto3

class DataBase():
    # Get the service resource.
    dynamodb = boto3.resource('dynamodb')
    # Get the service client
    dynamodb_client = boto3.client('dynamodb')

    primary_key = None

    def __init__(self, table_name):
        if table_name not in self.dynamodb_client.list_tables()['TableNames']:
            raise Exception(f"DynamoDB '{table_name}' does not exist!")
        else:
            self.table = self.dynamodb.Table(table_name)

        self.primary_key = self.table.key_schema[0]['AttributeName']
        
        return None

    def write(self, primary_key, key, value):
        self.table.put_item(
            Item={
                self.primary_key : primary_key,
                key : value
            }
        )

    def get(self, primary_key):
        response = self.table.get_item(
            Key={ 
               self.primary_key : primary_key
            }
        )
        try:
            return response['Item']
        except:
            return None

    def delete(self, primary_key):
        self.table.delete_item(
            Key={
                self.primary_key : primary_key
            }
        )

    def update(self, primary_key, key, value):
        self.table.update_item(
            Key={
                self.primary_key : primary_key
            },
            UpdateExpression=f'SET {key} = :val1',
            ExpressionAttributeValues={
                ':val1': value
            }
        )
