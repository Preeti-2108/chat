def construct_response(result):
    return {
        'status_code': result['status_code'],
        'body': result['body'],
        'headers': {
            'Content-Type': 'application/json'
        }
    }