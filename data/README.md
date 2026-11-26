# Bologna Case-Study Data

E5 uses a hybrid design: public pharmacy infrastructure and district
demographics are real, while worker availability, preferences, and home
districts are synthetic.

## Official sources

- `farmacie_bologna.csv`: Comune di Bologna, **Farmacie**, CC BY 4.0.
  https://opendata.comune.bologna.it/explore/dataset/farmacie/
- `popolazione.csv`: Comune di Bologna, resident population by age and
  quartiere, CC BY 4.0.
  https://opendata.comune.bologna.it/explore/dataset/popolazione-residente-per-eta-sesso-cittadinanza-quartiere-zona-area-statistica-/
- `quartieri.geojson`: Comune di Bologna, official quartiere boundaries,
  CC BY 4.0.
  https://opendata.comune.bologna.it/explore/dataset/quartieri-di-bologna/export/

Raw downloads belong in `data/raw/` and are intentionally ignored by Git.
Create the compact versioned tables with:

```powershell
python scripts/prepare_bologna_data.py
```

The preparation step maps the municipal pharmacy coordinates to quartieri by
a point-in-polygon operation. It does not infer districts from postcodes and
does not use random fallback. The snapshot date records when the source was
downloaded; it is not a guarantee that every listed pharmacy was open that day.

## Interpretation boundary

The municipal pharmacy list is not a night-duty schedule. E5 is therefore a
Bologna-grounded sensitivity scenario: at least one required service location
is selected per quartiere, additional locations are allocated using the number
of residents aged 65+ as a proxy, and real pharmacies rotate through those
slots. The proxy is not presented as observed night-pharmacy demand.
