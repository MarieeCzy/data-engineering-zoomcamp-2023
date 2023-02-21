from pathlib import Path
import pandas as pd
from prefect import flow,task
from prefect_gcp.cloud_storage import GcsBucket
from prefect.tasks import task_input_hash
from datetime import timedelta

@task(log_prints=True, retries=3, cache_key_fn=task_input_hash, cache_expiration=timedelta(days=1))
def fetch(dataset_url: str) -> pd.DataFrame:
    '''Read taaxi data from web into pandas DataFrame'''
    df = pd.read_csv(dataset_url)
    return df

@task(log_prints=True)
def clean(df: pd.DataFrame) -> pd.DataFrame:
    '''Fix some dtype issues'''
    df['tpep_pickup_datetime'] = pd.to_datetime(df['tpep_pickup_datetime'])
    df['tpep_dropoff_datetime'] = pd.to_datetime(df['tpep_dropoff_datetime'])
    print(df.head(2))
    print(f'columns: {df.dtypes}')
    print(df.shape)
    return df
 
@task(log_prints=True)
def write_local(df: pd.DataFrame, color: str, dataset_file: str) -> Path:
    '''Write DataFrame out locally as parquet file '''
    path = Path(f'data/{color}/{dataset_file}.parquet')
    df.to_parquet(path, compression='gzip')
    return path

@task(log_prints=True)
def write_gcs(path: Path) -> None:
    '''Uploading local parquet file to GCS'''
    gcs_block = GcsBucket.load("gcs-bucket")
    gcs_block.upload_from_path(from_path=path, to_path=path)
    return

@flow(log_prints=True)
def etl_web_to_gcs(year: int, month: int, color: str) -> None:
    '''The main ETL function'''
    dataset_file = f'{color}_tripdata_{year}-{month:02}'
    dataset_url = f'https://github.com/DataTalksClub/nyc-tlc-data/releases/download/{color}/{dataset_file}.csv.gz'
    
    df = fetch(dataset_url)
    clean_df = clean(df)
    path = write_local(clean_df, color, dataset_file)
    write_gcs(path)

@flow()
def etl_parent_flow(
    months: list[int], year: int = 2021, color: str = 'yellow'
):
    for month in months:
        etl_web_to_gcs(year, month, color)   

if __name__ == "__main__":
    color = 'yellow'
    months = [1,2,3]
    year = 2021
    etl_parent_flow(months, year, color)