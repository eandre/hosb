from encore.storage import postgres

# Encore provisions the database and applies ./migrations before the service
# starts.
db = postgres.Database("community", migrations="./migrations")
