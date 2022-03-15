# Databricks notebook source
# MAGIC %md
# MAGIC 
# MAGIC # Delta Demo
# MAGIC ## Ensuring Consistency with ACID Transactions with Delta Lake 
# MAGIC ## ==> Simplified Data Engineering, Increased Reliability/Stability, Lower TCO
# MAGIC 
# MAGIC <img src="https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-logo-whitebackground.png" width=200/>
# MAGIC 
# MAGIC ## The Data
# MAGIC 
# MAGIC The data used is public data from Lending Club. It includes all funded loans from 2012 to 2017. Each loan includes applicant information provided by the applicant as well as the current loan status (Current, Late, Fully Paid, etc.) and latest payment information. For a full view of the data please view the data dictionary available [here](https://resources.lendingclub.com/LCDataDictionary.xlsx).
# MAGIC 
# MAGIC 
# MAGIC ![Loan_Data](https://preview.ibb.co/d3tQ4R/Screen_Shot_2018_02_02_at_11_21_51_PM.png)
# MAGIC 
# MAGIC https://www.kaggle.com/wendykan/lending-club-loan-data

# COMMAND ----------

# MAGIC %md
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Reliability.png" alt="Reliability" width="1000">

# COMMAND ----------

# MAGIC %md ## 1/ Import Data and create pre-Delta Lake Table ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC * This will create a lot of small Parquet files emulating the typical small file problem that occurs with streaming or highly transactional data

# COMMAND ----------

# MAGIC %sql
# MAGIC CREATE DATABASE IF NOT EXISTS kd_delta;
# MAGIC USE kd_delta;

# COMMAND ----------

# DBTITLE 0,Import Data and create pre-Databricks Delta Table
# -----------------------------------------------
# Uncomment and run if this folder does not exist
# -----------------------------------------------

from pyspark.sql.functions import monotonically_increasing_id 
from pyspark.sql.types import LongType
spark.conf.set("spark.databricks.delta.retentionDurationCheck.enabled", False)

data = spark.read.parquet("/databricks-datasets/samples/lending_club/parquet/")

# Optionally, reduce the amount of data (to run on DBCE) 
(loan_stats, loan_stats_rest) = data.randomSplit([1.0, 0.0], seed=123)

# Select only the columns needed
loan_stats = loan_stats.select("addr_state", "loan_status", "loan_amnt", "grade") \
.withColumn("loan_amnt", loan_stats["loan_amnt"].cast(LongType())) \
.withColumn("id", monotonically_increasing_id())

loan_stats.write.mode("overwrite") \
.format("parquet") \
.save("dbfs:/ml/loan_stats.parquet")

#print(data.count(), loan_stats.count(), loan_stats_rest.count())

# COMMAND ----------

# MAGIC %md 
# MAGIC ## 2/ Easily Convert Parquet to Delta Lake format ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC With Delta Lake, you can easily transform your Parquet data into Delta Lake format. 

# COMMAND ----------

# MAGIC %sql
# MAGIC -- DROP TABLE IF EXISTS loan_stats;
# MAGIC -- DROP TABLE IF EXISTS loan_stats_delta;
# MAGIC -- Parquet table creation
# MAGIC CREATE TABLE loan_stats
# MAGIC USING parquet
# MAGIC LOCATION '/ml/loan_stats.parquet';
# MAGIC 
# MAGIC -- Converting an existing parquet table to delta
# MAGIC CREATE TABLE loan_stats_delta
# MAGIC USING delta
# MAGIC AS SELECT * FROM loan_stats;

# COMMAND ----------

# MAGIC %sql
# MAGIC -- View Delta Lake table
# MAGIC SELECT * FROM loan_stats_delta limit 25;

# COMMAND ----------

# MAGIC %sql 
# MAGIC DESCRIBE DETAIL loan_stats_delta

# COMMAND ----------

# MAGIC %sql
# MAGIC DELETE FROM loan_stats_delta WHERE addr_state IN ('debt_consolidation', '531xx', 'IA'); 

# COMMAND ----------

# MAGIC %md ### 2.1/ Auto Loader ==> Rapid At Scale Migration
# MAGIC 
# MAGIC <img src="https://github.com/koundinyabs/databricks-demo/raw/main/AutoLoader.png" alt="Reliability" width="1000">

# COMMAND ----------

# MAGIC %md ## 3/ Unified Batch and Streaming Source and Sink ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC These cells showcase streaming and batch concurrent queries (inserts and reads)
# MAGIC * This notebook will run an `INSERT` every 10s against our `loan_stats_delta` table
# MAGIC * We will run two streaming queries concurrently against this data

# COMMAND ----------

DELTALAKE_SILVER_PATH = "/user/hive/warehouse/kd_delta.db/loan_stats_delta"

# COMMAND ----------

# Read the insertion of data
loan_by_state_readStream = spark.readStream.format("delta").load(DELTALAKE_SILVER_PATH)
loan_by_state_readStream.createOrReplaceTempView("loan_stats_readStream")
#Note: Stop the notebook before the streaming cell, in case of a "run all"
dbutils.notebook.exit("stop") 

# COMMAND ----------

# MAGIC %sql
# MAGIC select addr_state, sum(`loan_amnt`) as total_amount from loan_stats_readStream group by addr_state

# COMMAND ----------

# MAGIC %md **Wait** until the stream is up and running
# MAGIC 
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Streaming-Query.png" width="783">
# MAGIC 
# MAGIC before executing the code below

# COMMAND ----------

import time
i = 1
while i <= 6:
  # Execute Insert statement
  spark.sql("INSERT INTO loan_stats_delta VALUES ('IA', 'Fully Paid', 10000000, 'A', 1)")

  print('loan_by_state_delta: inserted new row of data, loop: [%s]' % i)
      
  # Loop through
  i = i + 1
  time.sleep(1)

# COMMAND ----------

# MAGIC %md Observe that the Iowa (middle state) has the largest number of loans due to the recent stream of data.  Note that the original `loan_stats_delta` table is updated as we're reading `loan_by_state_readStream`.
# MAGIC 
# MAGIC ##### Once the previous cell is finished and the state of Iowa is fully populated in the map, click *Cancel* to stop the `readStream`.
# MAGIC 
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Streaming-Query-Cancel.png" width="783">

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4/ Full DML Support ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC Delta Lake supports standard DML including UPDATE, DELETE and MERGE INTO providing developers more controls to manage their big datasets.

# COMMAND ----------

# MAGIC %md ### 4.1/ DELETE Support ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC The data was originally supposed to be assigned to `WA` state, so let's `DELETE` those values assigned to `IA`

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Running `DELETE` on the Delta Lake table
# MAGIC DELETE FROM loan_stats_delta WHERE addr_state = 'IA'

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Review current loans within the `loan_by_state_delta` Delta Lake table
# MAGIC select addr_state, sum(`loan_amnt`) as total_amount from loan_stats_delta group by addr_state

# COMMAND ----------

# MAGIC %md ### 4.2/ UPDATE Support ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png) 
# MAGIC The data was originally supposed to be assigned to `WA` state, so let's `UPDATE` those values

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Running `UPDATE` on the Delta Lake table
# MAGIC UPDATE loan_stats_delta SET `loan_status` = 'Fully Paid' WHERE addr_state = 'WA'

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Review current loans within the `loan_by_state_delta` Delta Lake table
# MAGIC select * from loan_stats_delta where addr_state='WA'

# COMMAND ----------

# MAGIC %md ### 4.3/ MERGE INTO Support ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC #### INSERT or UPDATE parquet: 7-step process
# MAGIC 
# MAGIC With a legacy data pipeline, to insert or update a table, you must:
# MAGIC 1. Identify the new rows to be inserted
# MAGIC 2. Identify the rows that will be replaced (i.e. updated)
# MAGIC 3. Identify all of the rows that are not impacted by the insert or update
# MAGIC 4. Create a new temp based on all three insert statements
# MAGIC 5. Delete the original table (and all of those associated files)
# MAGIC 6. "Rename" the temp table back to the original table name
# MAGIC 7. Drop the temp table
# MAGIC 
# MAGIC ![](https://pages.databricks.com/rs/094-YMS-629/images/merge-into-legacy.gif)
# MAGIC 
# MAGIC 
# MAGIC #### INSERT or UPDATE with Delta Lake
# MAGIC 
# MAGIC 2-step process: 
# MAGIC 1. Identify rows to insert or update
# MAGIC 2. Use `MERGE`
# MAGIC 
# MAGIC #### We'll be using the loan_stats_delta table and merge new data into it. Let's review our columns:

# COMMAND ----------

# MAGIC %sql
# MAGIC delete from loan_stats_delta where id in (1,2);
# MAGIC insert into loan_stats_delta values ("PARIS", "Fully Paid", 100, "A", 1);
# MAGIC 
# MAGIC -- create an update table
# MAGIC drop table if exists update_loan_delta; 
# MAGIC create table update_loan_delta 
# MAGIC  (`addr_state` STRING, `loan_status` STRING, `loan_amnt` FLOAT, `grade` STRING, `id` BIGINT)
# MAGIC  USING DELTA;
# MAGIC 
# MAGIC -- insert some data in my update table
# MAGIC insert into update_loan_delta values ("PARIS", "Fuly Paid", 999, "D", 1);
# MAGIC insert into update_loan_delta values ("PARIS", "Fuly Paid", 100, "A", 2);

# COMMAND ----------

# MAGIC %sql
# MAGIC select * from loan_stats_delta where id in (1,2) order by id

# COMMAND ----------

# MAGIC %sql
# MAGIC select * from update_loan_delta order by id

# COMMAND ----------

# MAGIC %md 
# MAGIC ### Let's use the SQL MERGE command to update the existing values and insert the new one:

# COMMAND ----------

# MAGIC %sql
# MAGIC MERGE INTO loan_stats_delta
# MAGIC USING update_loan_delta
# MAGIC ON loan_stats_delta.id = update_loan_delta.id
# MAGIC WHEN MATCHED THEN
# MAGIC     UPDATE SET loan_stats_delta.loan_amnt = update_loan_delta.loan_amnt
# MAGIC WHEN NOT MATCHED
# MAGIC     THEN INSERT *

# COMMAND ----------

# MAGIC %sql 
# MAGIC select * from loan_stats_delta where id in (1, 2) order by id

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5/ Data Quality ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.1/ Schema enforcement with Delta Lake ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)

# COMMAND ----------

# MAGIC %md ** ==> Delta protects against data corruption and automatically do schema enforcement on write!**

# COMMAND ----------

#          addr_state  loan_status   loan_amnt  grade id
items =   [('PARIS',   "fully Paid", "2500",    "A",  9999998),
           ('PARIS',   "fully Paid", "13",      "A",  9999999)]
incorrect_data = spark.createDataFrame(items, ['addr_state', 'loan_status', 'loan_amnt', 'grade', 'id'])
incorrect_data.write.format("delta").mode("append").save(DELTALAKE_SILVER_PATH)

# COMMAND ----------

# MAGIC %md
# MAGIC ### 5.2/ Schema Evolution ![Delta Lake Logo Tiny](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC With the `mergeSchema` option, you can evolve your Delta Lake table schema

# COMMAND ----------

# Generate new loans with zip code
#          addr_state  loan_status   loan_amnt  grade zip_code  id
items =   [('PARIS',   "fully Paid", 2500,    "A",  "75010",  9999998),
           ('PARIS',   "fully Paid", 13,      "A",  "75010",  9999999)]
data_with_zip_code = spark.createDataFrame(items, ['addr_state', 'loan_status', 'loan_amnt', 'grade', 'zip_code', 'id'])

display(data_with_zip_code)

# COMMAND ----------

# Let's write this data out to our Delta table
data_with_zip_code.write.format("delta").mode("append").save(DELTALAKE_SILVER_PATH)

# COMMAND ----------

# MAGIC %md **Note**: This command fails because the schema of our new data does not match the schema of our original data

# COMMAND ----------

# Add the mergeSchema option
data_with_zip_code.write.option("mergeSchema","true").format("delta").mode("append").save(DELTALAKE_SILVER_PATH)

# COMMAND ----------

# MAGIC %md **Note**: With the `mergeSchema` option, we can merge these different schemas together.

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Review current loans within the `loan_by_state_delta` Delta Lake table
# MAGIC SELECT * FROM loan_stats_delta
# MAGIC WHERE zip_code IS NOT null
# MAGIC ORDER BY id DESC

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY loan_stats_delta;

# COMMAND ----------

# MAGIC %md ## 6/ Let's Travel back in Time! ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC Databricks Delta’s time travel capabilities simplify building data pipelines for the following use cases. 
# MAGIC 
# MAGIC * Audit Data Changes
# MAGIC * Reproduce experiments & reports
# MAGIC * Rollbacks
# MAGIC 
# MAGIC As you write into a Delta table or directory, every operation is automatically versioned.
# MAGIC 
# MAGIC You can query by:
# MAGIC 1. Using a timestamp
# MAGIC 1. Using a version number
# MAGIC 
# MAGIC using Python, Scala, and/or Scala syntax; for these examples we will use the SQL syntax.  
# MAGIC 
# MAGIC For more information, refer to [Introducing Delta Time Travel for Large Scale Data Lakes](https://databricks.com/blog/2019/02/04/introducing-delta-time-travel-for-large-scale-data-lakes.html)

# COMMAND ----------

# MAGIC %md ### 6.1/ Review Delta Lake Table History ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC All the transactions for this table are stored within this table including the initial set of insertions, update, delete, merge, and inserts with schema modification

# COMMAND ----------

# MAGIC %sql
# MAGIC INSERT INTO loan_stats_delta VALUES ('IA', 'Fully Paid', 1000000, 99999998, '12345', '75010');
# MAGIC INSERT INTO loan_stats_delta VALUES ('IA', 'Fully Paid', 10000, 99999999, '98765', '75010');
# MAGIC DELETE FROM loan_stats_delta WHERE addr_state='IA';

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY loan_stats_delta

# COMMAND ----------

# MAGIC %md ### 6.2/ Time Travel via Version Number ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC Below are SQL syntax examples of Delta Time Travel by using a Version Number

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * FROM loan_stats_delta VERSION AS OF 14 WHERE addr_state="IA" LIMIT 10

# COMMAND ----------

# MAGIC %sql
# MAGIC --first version doesn't contains the zip code!
# MAGIC SELECT * FROM loan_stats_delta VERSION AS OF 0 limit 10

# COMMAND ----------

# MAGIC %md ## 7/ Run concurrent queries with ACID transactions ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC Using DELTA, you can safely run concurrent requests. One of them will rollback if two processes update the same data!

# COMMAND ----------

# MAGIC %md
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Atomicity.png" alt="Atomicity" width="1000">

# COMMAND ----------

# MAGIC %md
# MAGIC **Let's create a new `loanstats_concurrent_delta` we'll be using for our tests:**

# COMMAND ----------

loan_stats.write.partitionBy("addr_state").format("delta").option("overwriteSchema", "true").mode("overwrite").save("/ml/demo_delta/loanstats_concurrent_delta.delta")


# COMMAND ----------

# MAGIC %sql
# MAGIC drop table if exists loan_delta_concurrent;
# MAGIC CREATE TABLE loan_delta_concurrent
# MAGIC USING delta
# MAGIC LOCATION '/ml/demo_delta/loanstats_concurrent_delta.delta';

# COMMAND ----------

# DBTITLE 1,ACID Transactions: Running Concurrent (non-conflicting) UPDATEs on the table at the same time
import threading, time

def update_ca_data():
  spark.sql("update loan_delta_concurrent set grade='A' where addr_state='CA'")
def update_wa_data():
  spark.sql("update loan_delta_concurrent set grade='A' where addr_state='WA'")
  
thread = threading.Thread(target=update_ca_data)
thread.start()
time.sleep(1)
thread2 = threading.Thread(target=update_wa_data)
thread2.start()
thread.join()
thread2.join()


# COMMAND ----------

# MAGIC %sql
# MAGIC select * from loan_delta_concurrent where addr_state="CA" limit 10;

# COMMAND ----------

# MAGIC %sql
# MAGIC DESCRIBE HISTORY loan_delta_concurrent;

# COMMAND ----------

# MAGIC %md ** ==> You can safely run concurrent requests, all your queries run as ACID transactions with a Write Serializable isolation level by default ! **

# COMMAND ----------

# MAGIC %md
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Performance.png" alt="Performance" width="1000">

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ## 8/ Performance boost in Delta ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC Read are much faster using delta. Let's see how it works !

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ### 8.1/ Compaction with Delta ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)

# COMMAND ----------

# DBTITLE 1,Let's simulate a table having lots of very small file:
loan_stats.repartition(1000).write.format("delta").mode("overwrite").save("/ml/demo_delta/loanstats_perf_delta.delta")

# COMMAND ----------

len(dbutils.fs.ls('/ml/demo_delta/loanstats_perf_delta.delta'))

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP TABLE IF EXISTS loan_perf_delta;
# MAGIC CREATE TABLE loan_perf_delta
# MAGIC USING delta
# MAGIC LOCATION '/ml/demo_delta/loanstats_perf_delta.delta';

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Compaction.png" alt="Compaction" width="1000">

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * from loan_perf_delta where addr_state='NY' and grade='A';

# COMMAND ----------

# DBTITLE 1,Having a lot of small files hurt performances! We can run OPTIMIZE to compact them all !
# MAGIC %sql
# MAGIC OPTIMIZE loan_perf_delta;
# MAGIC -- Vacuum will clean the history to only keep the new files
# MAGIC VACUUM loan_perf_delta RETAIN 0 HOURS;

# COMMAND ----------

# MAGIC %fs ls /ml/demo_delta/loanstats_perf_delta.delta

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * from loan_perf_delta where addr_state='NY' and grade='A';

# COMMAND ----------

# DBTITLE 1,Auto-Optimized Writes
# MAGIC %md
# MAGIC 
# MAGIC `alter table loan_stats_delta set tblproperties ('delta.autoOptimize.autoCompact' = true, 'delta.autoOptimize.optimizeWrite' = true);`
# MAGIC 
# MAGIC ![Auto-Optimized Writes](https://docs.databricks.com/_images/optimized-writes.png) 

# COMMAND ----------

# MAGIC %md
# MAGIC 
# MAGIC ###  8.2/ ZORDER with Delta ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC <img src="https://arduino-databricks-public-s3-paris.s3.eu-west-3.amazonaws.com/Delta_Workshop/Delta-Zorder.png" alt="Zorder" width="1000">

# COMMAND ----------

# DBTITLE 1,Zorder can further decrease our read time by collocating similar data:
# MAGIC %sql
# MAGIC OPTIMIZE loan_perf_delta ZORDER BY (addr_state, grade);
# MAGIC -- Super efficient queries as tabled are now ZORDERED by addr_state and grade!

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT * from loan_perf_delta where addr_state='NY' and grade='A';

# COMMAND ----------

# MAGIC %md 
# MAGIC ### 8.3/ Scalable metadata  ![Delta Lake Tiny Logo](https://pages.databricks.com/rs/094-YMS-629/images/delta-lake-tiny-logo.png)
# MAGIC 
# MAGIC Our table metadata is now stored in a parquet checkpoint file, no need to list all the files or aggressively query the metastore

# COMMAND ----------

# MAGIC %fs ls /ml/demo_delta/loanstats_perf_delta.delta/_delta_log/

# COMMAND ----------

# MAGIC %sh cat /dbfs/ml/demo_delta/loanstats_perf_delta.delta/_delta_log/00000000000000000000.json

# COMMAND ----------

# MAGIC %md ** ==> Combining delta, zorder, data skipping and local caching, we can reach x100 read speed on TB of data ! **

# COMMAND ----------

# MAGIC %md ## 9/ Demo Cleanup

# COMMAND ----------

# MAGIC %sql
# MAGIC DROP DATABASE IF EXISTS kd_delta CASCADE;
