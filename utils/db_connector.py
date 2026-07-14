import motor.motor_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text, inspect
import asyncio

class SQLConnector:
    def __init__(self, connection_string: str):
        # Force asyncpg driver for PostgreSQL
        if connection_string.startswith("postgres://"):
            connection_string = connection_string.replace("postgres://", "postgresql+asyncpg://", 1)
        elif connection_string.startswith("postgresql://"):
            connection_string = connection_string.replace("postgresql://", "postgresql+asyncpg://", 1)
            
        self.engine = create_async_engine(connection_string, echo=False)
        
    async def test_connection(self):
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
        
    async def get_schema(self):
        # We must run synchronous reflection in a thread pool
        def _get_tables(conn):
            inspector = inspect(conn)
            tables = inspector.get_table_names()
            schema = {}
            for table in tables:
                columns = inspector.get_columns(table)
                schema[table] = [{"name": c["name"], "type": str(c["type"])} for c in columns]
            return schema

        async with self.engine.connect() as conn:
            schema = await conn.run_sync(_get_tables)
            return schema
            
    async def execute_query(self, query: str, limit: int = 100):
        async with self.engine.connect() as conn:
            result = await conn.execute(text(query))
            keys = list(result.keys())
            rows = result.fetchmany(limit)
            return [dict(zip(keys, row)) for row in rows]

class MongoConnector:
    def __init__(self, connection_string: str, db_name: str = None):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(
            connection_string, 
            serverSelectionTimeoutMS=5000,
            tlsAllowInvalidCertificates=True
        )
        self.db_name = db_name
        
    async def test_connection(self):
        await self.client.server_info()
        return True
        
    async def get_schema(self):
        schema = {}
        # If no specific db, iterate over all non-system databases
        try:
            db_names = [self.db_name] if self.db_name and self.db_name != "test_db" else await self.client.list_database_names()
        except Exception:
            db_names = await self.client.list_database_names()

        for d_name in db_names:
            if d_name in ["admin", "local", "config", "test_db"]:
                continue
            db = self.client[d_name]
            collections = await db.list_collection_names()
            for coll in collections:
                # Format: db_name.collection_name so we know where it came from
                target_name = f"{d_name}.{coll}"
                sample = await db[coll].find_one()
                if sample:
                    schema[target_name] = [{"name": k, "type": type(v).__name__} for k, v in sample.items()]
                else:
                    schema[target_name] = []
        return schema
        
    async def execute_query(self, collection_name: str, filter_query: dict, limit: int = 100):
        # collection_name is formatted as "db_name.collection_name"
        if "." in collection_name:
            d_name, c_name = collection_name.split(".", 1)
            db = self.client[d_name]
            collection = db[c_name]
        else:
            # fallback
            db = self.client.get_default_database()
            collection = db[collection_name]
            
        cursor = collection.find(filter_query).limit(limit)
        results = []
        for doc in await cursor.to_list(length=limit):
            doc['_id'] = str(doc['_id'])
            results.append(doc)
        return results
