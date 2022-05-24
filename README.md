# tap-opsgenie

This is a [Singer](https://singer.io) tap that produces JSON-formatted
data from the GitHub API following the [Singer
spec](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md).

This tap:
- Pulls raw data from the [OpsGenie REST API](https://docs.opsgenie.com/docs/api-overview)
- Extracts the following resources from OpsGenie:
  - [Alerts](https://docs.opsgenie.com/docs/alert-api#list-alerts)
- Outputs the schema for each resource
- Incrementally pulls data based on the input state

## Quick start

1. Install

    ```bash
    pip install tap-opsgenie
    ```

2. Create your OpsGenie API token
    
    You might need admin credentials for this. Log into your OpsGenie account. Navigate to "Settings" and "Integrations". 
    Either use the API token from the "Default API" integration or create a new API integration by clicking on 
    "Add integration".

3. Create the config file

    Take `config.json.dist` in this repo as a template. The `query` key has to contain the search query that matches
    all alerts you want to extract. The query syntax is 
    [documented here](https://support.atlassian.com/opsgenie/docs/search-queries-for-alerts/).
    
    **Important**: This tap uses the `updatedAt` field to incrementally load data from OpsGenie. You cannot use the `updatedAt` field in your own query.

4. Discover the catalog

    Run the tap in discovery mode to build the catalog file.
    
    ```bash
    tap-opsgenie --config config.json --discover > catalog.json
    ```

5. Select the streams to sync

    By default the tap will skip all streams. In the `catalog.json` file you find all the streams with a schema attached. Each schema you want to sync needs an additional parameter: `"selected": true`

```
{
  "streams": [
    {
      "tap_stream_id": "alerts",
      "replication_key": "updatedAt",
      "replication_method": "INCREMENTAL",
      "key_properties": [
        "tinyId"
      ],
      "schema": {
        "selected": true,
        "properties": {
          "id": {
            "type": "string"
          },
          [...]
```

6. Create an empty state file

    Create a file called `state.json` and place an empty object in it.

    ```json
    {}
    ```
   
    The state file will keep track on where the tap left off syncing the last time it was run and on the next run only
    sync alerts that were updated after the timestamp of the last run

7. Run the tap

    ```bash
    tap-opsgenie --config config.json --catalog catalog.json --state state.json
    ```