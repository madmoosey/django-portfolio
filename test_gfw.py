import requests

api_key = "6f400f15-bac8-4c76-8f54-4567a49afaed"
url = "https://data-api.globalforestwatch.org/dataset/umd_tree_cover_loss/v1.13/query/json?sql=SELECT+umd_tree_cover_loss__year%2C+SUM%28umd_tree_cover_loss__ha%29+as+area_ha+FROM+data+WHERE+iso+%3D+%27USA%27+AND+adm1+%3D+%2713%27+AND+adm2+%3D+%2713013%27+GROUP+BY+umd_tree_cover_loss__year"

print("Testing with x-api-key...")
resp1 = requests.get(url, headers={"x-api-key": api_key})
print(resp1.status_code, resp1.text[:200])

print("Testing with Bearer...")
resp2 = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
print(resp2.status_code, resp2.text[:200])

