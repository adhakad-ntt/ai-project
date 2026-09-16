from services.project_service import slug

def test_slug():
    assert slug('My Demo Project')=='my-demo-project'
