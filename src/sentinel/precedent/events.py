"""Curated library of historical market events (public record). `reaction` is the first trading day on which
markets could react (weekend and after-hours announcements point to the next session).

Dates come from the public record and were compiled with AI assistance: the README tells reviewers to spot-check them.
Reactions are NOT typed in: every number PRECEDENT reports is computed from real price and rate history.
"""
EVENTS = [
    # (event date, reaction date, type, region, title)
    ("2001-09-11", "2001-09-17", "Geopolitical", "US", "Terror attacks on New York and Washington; US markets closed until September 17"),
    ("2003-03-20", "2003-03-20", "Geopolitical", "Middle East", "US-led coalition begins the invasion of Iraq"),
    ("2014-03-03", "2014-03-03", "Geopolitical", "Europe", "Russia moves troops into Crimea"),
    ("2016-06-24", "2016-06-24", "Geopolitical", "Europe", "UK votes to leave the European Union (Brexit)"),
    ("2016-11-09", "2016-11-09", "Geopolitical", "US", "Donald Trump wins the US presidential election"),
    ("2018-03-22", "2018-03-22", "Geopolitical", "US/China", "US announces tariffs on Chinese imports, opening the trade war"),
    ("2019-05-05", "2019-05-06", "Geopolitical", "US/China", "Trump threatens higher tariffs on Chinese goods as trade talks falter"),
    ("2019-08-05", "2019-08-05", "Geopolitical", "US/China", "China lets the yuan weaken past 7 per dollar; US labels China a currency manipulator"),
    ("2019-09-14", "2019-09-16", "Geopolitical", "Middle East", "Drone attacks hit Saudi Aramco's Abqaiq oil processing facility"),
    ("2020-01-03", "2020-01-03", "Geopolitical", "Middle East", "US drone strike kills Iranian general Qassem Soleimani"),
    ("2022-02-24", "2022-02-24", "Geopolitical", "Europe", "Russia launches a full-scale invasion of Ukraine"),
    ("2023-10-07", "2023-10-09", "Geopolitical", "Middle East", "Hamas attacks Israel and war begins in Gaza"),
    ("2025-04-02", "2025-04-03", "Geopolitical", "Global", "US announces sweeping reciprocal tariffs on trading partners"),
    ("2025-04-09", "2025-04-09", "Geopolitical", "Global", "US pauses most reciprocal tariffs for 90 days"),

    ("2008-09-29", "2008-09-29", "Macroeconomic", "US", "US House rejects the 700 billion dollar bank bailout"),
    ("2010-05-06", "2010-05-06", "Macroeconomic", "US", "Flash crash: the Dow falls about 1,000 points within minutes"),
    ("2012-07-26", "2012-07-26", "Macroeconomic", "Europe", "ECB president Draghi pledges to do whatever is needed to preserve the euro"),
    ("2013-05-22", "2013-05-22", "Macroeconomic", "US", "Fed chair Bernanke signals QE tapering and triggers the taper tantrum"),
    ("2014-11-27", "2014-11-28", "Macroeconomic", "Global", "OPEC declines to cut output as oil prices slide"),
    ("2015-01-15", "2015-01-15", "Macroeconomic", "Europe", "Swiss National Bank abandons the euro peg and the franc surges"),
    ("2015-08-24", "2015-08-24", "Macroeconomic", "Asia", "Global equity selloff on China growth fears; US stocks plunge at the open"),
    ("2016-01-04", "2016-01-04", "Macroeconomic", "Asia", "China halts trading after a circuit breaker triggers on the first trading day of 2016"),
    ("2018-02-05", "2018-02-05", "Macroeconomic", "US", "Volatility spike: the VIX nearly doubles and the S&P 500 falls over 4 percent"),
    ("2020-03-08", "2020-03-09", "Macroeconomic", "Middle East", "Saudi Arabia launches an oil price war after OPEC+ talks collapse"),
    ("2020-03-11", "2020-03-11", "Macroeconomic", "Global", "WHO declares COVID-19 a pandemic"),
    ("2020-03-15", "2020-03-16", "Macroeconomic", "US", "Fed cuts rates to zero and restarts QE in an emergency Sunday move"),
    ("2020-04-20", "2020-04-20", "Macroeconomic", "US", "US crude oil futures turn negative for the first time"),
    ("2021-11-26", "2021-11-26", "Macroeconomic", "Global", "Omicron variant detected and global markets sell off"),
    ("2022-03-16", "2022-03-16", "Macroeconomic", "US", "Fed raises interest rates for the first time since 2018"),
    ("2022-06-15", "2022-06-15", "Macroeconomic", "US", "Fed delivers a 75 basis point rate hike, its largest since 1994"),
    ("2022-09-23", "2022-09-23", "Macroeconomic", "UK", "UK mini-budget triggers gilt market turmoil"),
    ("2024-08-05", "2024-08-05", "Macroeconomic", "Asia", "Global selloff as the yen carry trade unwinds and recession fears rise"),

    ("2007-08-09", "2007-08-09", "Credit Event", "Europe", "BNP Paribas freezes funds, signalling the start of the credit crisis"),
    ("2008-03-16", "2008-03-17", "Credit Event", "US", "Bear Stearns rescued by JPMorgan with Federal Reserve backing"),
    ("2008-09-07", "2008-09-08", "Credit Event", "US", "US takes Fannie Mae and Freddie Mac into conservatorship"),
    ("2008-09-15", "2008-09-15", "Credit Event", "US", "Lehman Brothers files for bankruptcy"),
    ("2011-08-05", "2011-08-08", "Credit Event", "US", "S&P downgrades the US credit rating from AAA to AA+"),
    ("2021-03-26", "2021-03-29", "Credit Event", "US", "Archegos collapse triggers forced selling and bank losses"),
    ("2021-09-20", "2021-09-20", "Credit Event", "Asia", "Evergrande default fears spark a global selloff"),
    ("2022-11-11", "2022-11-11", "Credit Event", "US", "FTX files for bankruptcy"),
    ("2023-03-10", "2023-03-10", "Credit Event", "US", "Silicon Valley Bank collapses and is taken over by regulators"),
    ("2023-05-01", "2023-05-01", "Credit Event", "US", "First Republic Bank is seized and sold to JPMorgan"),
    ("2023-08-01", "2023-08-02", "Credit Event", "US", "Fitch downgrades the US credit rating to AA+"),

    ("2016-06-13", "2016-06-13", "Merger/Acquisition", "US", "Microsoft agrees to buy LinkedIn for about 26 billion dollars"),
    ("2017-12-14", "2017-12-14", "Merger/Acquisition", "US", "Disney agrees to buy 21st Century Fox assets for about 52 billion dollars"),
    ("2023-03-19", "2023-03-20", "Merger/Acquisition", "Europe", "UBS agrees an emergency takeover of Credit Suisse"),
    ("2023-10-11", "2023-10-11", "Merger/Acquisition", "US", "Exxon Mobil agrees to buy Pioneer Natural Resources for about 60 billion dollars"),
    ("2023-10-23", "2023-10-23", "Merger/Acquisition", "US", "Chevron agrees to buy Hess for about 53 billion dollars"),

    ("2010-07-21", "2010-07-21", "Regulatory", "US", "Dodd-Frank Act signed into law, tightening bank regulation"),
    ("2021-07-23", "2021-07-26", "Regulatory", "Asia", "China unveils a crackdown on private tutoring and Chinese tech stocks slump"),
    ("2023-06-05", "2023-06-05", "Regulatory", "US", "SEC sues Binance, followed a day later by Coinbase, over unregistered securities"),

    ("2021-03-23", "2021-03-23", "Supply Chain", "Global", "Container ship Ever Given blocks the Suez Canal"),
    ("2022-03-28", "2022-03-28", "Supply Chain", "Asia", "Shanghai begins a phased COVID lockdown, disrupting global supply chains"),

    ("2017-05-12", "2017-05-15", "Cyber", "Global", "WannaCry ransomware spreads worldwide"),
    ("2020-12-13", "2020-12-14", "Cyber", "US", "SolarWinds supply-chain hack is disclosed"),
    ("2021-05-07", "2021-05-10", "Cyber", "US", "Colonial Pipeline shut down by a ransomware attack"),

    ("2005-08-29", "2005-08-29", "Natural Disaster", "US", "Hurricane Katrina strikes the US Gulf Coast"),
    ("2011-03-11", "2011-03-11", "Natural Disaster", "Asia", "Magnitude 9.0 earthquake and tsunami hit Japan"),
    ("2012-10-29", "2012-10-31", "Natural Disaster", "US", "Superstorm Sandy shuts US markets for two days"),
    ("2017-08-25", "2017-08-28", "Natural Disaster", "US", "Hurricane Harvey makes landfall in Texas and shuts refineries"),

    ("2007-01-09", "2007-01-09", "Product Launch", "US", "Apple unveils the iPhone"),
    ("2010-01-27", "2010-01-27", "Product Launch", "US", "Apple unveils the iPad"),
    ("2023-06-05", "2023-06-05", "Product Launch", "US", "Apple unveils the Vision Pro headset"),
    ("2025-01-27", "2025-01-27", "Product Launch", "Asia", "DeepSeek's low-cost AI model triggers a global tech selloff"),

    ("2022-04-19", "2022-04-20", "Earnings", "US", "Netflix reports its first subscriber loss in a decade and shares plunge"),
    ("2022-10-26", "2022-10-27", "Earnings", "US", "Meta results and spending plans send shares sharply lower"),
    ("2023-05-24", "2023-05-25", "Earnings", "US", "Nvidia issues blowout guidance on AI demand"),
]


def event_id(date: str, title: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:40].strip("-")
    return f"{date}-{slug}"


def library_rows() -> list:
    return [{"id": event_id(d, t), "event_date": d, "reaction_date": r, "event_type": ty, "region": rg,
             "title": t, "summary": f"{t}. Region: {rg}. Type: {ty}."} for d, r, ty, rg, t in EVENTS]
