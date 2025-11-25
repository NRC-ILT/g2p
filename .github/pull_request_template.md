Pull request template for adding a new language
-----------------------------------------------

<!--
  - Use this template if you are adding a new language or modifying a mapping
  - For all other PRs, please add  ?expand=1&template=software_pr.md  to the URL above
    to use the software PR template instead.
 -->

* **Please check if the PR fulfills these requirements**
- [ ] Mapping files are added in `g2p/mappings/langs`
- [ ] Mapping is either added to an existing folder or a new folder has been added
- [ ] Language folder and files use appropriate [ISO 639-3 codes](https://en.wikipedia.org/wiki/List_of_ISO_639-3_codes)
- [ ] `config-g2p.yaml` file includes all author names, and settings necessary
- [ ] Please add some test data in `g2p/tests/public/data`. The added file should be a csv/tsv/psv file and each row should have the format `[input_mapping_code,output_mapping_code,input_string,output_string]`
- [ ] As the last step, G2P has been updated by running `g2p update` locally and committing the change
- [ ] You agree to license your contribution under the same license as this project (see [LICENSE](https://github.com/NRC-ILT/g2p/blob/main/LICENSE) file).

* **Other information**:
