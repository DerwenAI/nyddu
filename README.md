# nyddu

spider-ish analysis, reporting, semantic content search/recsys.

  * `1_demo.py`: crawl a given website, producing a report in JSON
  * `2_load.py`: load the JSON report into `KùzuDB` with indexing for semantic search
  * `3_route.py`: render HTML pages to expore the report as a `FastAPI` router
