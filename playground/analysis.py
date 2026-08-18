#%%
import pandas

df = pandas.read_json('data.json')

df.head()
# %%
df.describe()
# %%
df['roles']
# %%
df['roles'].describe()
# %%
df.roles.count()
# %%
