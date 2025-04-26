# Saflii Scraper

Scrape the Saflii database: https://www.saflii.org/

## Documentation

### Setup
#### Hetzner Server
#### Python installieren
#### UV Installieren
#### Projekt erstellen
1. uv init saflii
2. 


#### Crawlee

### Saflii

#### Scraper Link Scheme

Es ist ein sehr einfaches Muster.

1. Journals, Gazettes, Rolls etc. sollen NICHT ignoriert werden.
2. Alle Links zu den einzelnen Gerichten sind hier zu finden: `https://www.saflii.org/content/databases.html`
   2.1. Relevant sind die Links zu den einzelnen Gerichten und anderen Institutionen, die in der HTML-Tabelle zu finden sind (XPATH: /html/body/div[3]/div/div[1]/div[2]/div/div[1]/div/div/table/tbody/tr[1]/td/a). Von hier aus sollte der Crawler zu den einzelnen Gerichten und Institutionen navigieren. Wichtig diese Liste kann sich ändern. Deshalb ist es wichtig, dass der Crawler immer wieder die Liste abruft und die Links aktualisiert wenn man automatisch ALLE Dokumente speichern möchte:

                <div class="accordion-body">
                  <table class="table table-striped table-bordered rounded">
                    <tbody>
                    <tr><td><a href="/za/journals/ADRY" class="link-secondary">South Africa: African Disability Rights Yearbook </a></td></tr>
                    <tr><td><a href="/za/journals/AHRLJ" class="link-secondary">South Africa: African Human Rights Law Journal </a></td></tr>
                    <tr><td><a href="/za/journals/ALR" class="link-secondary">South Africa: African Law Review </a></td></tr>
                    <tr><td><a href="/za/cases/ZACAC" class="link-secondary">South Africa: Competition Appeal Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZACT" class="link-secondary">South Africa: Competition Tribunal</a></td></tr>
                    <tr><td><a href="/za/cases/ZACONAF" class="link-secondary">South Africa: Consumer Affairs Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZACGSO" class="link-secondary">South Africa: Consumer Goods and Services Ombud</a></td></tr>
                    <tr><td><a href="/za/cases/ZACC" class="link-secondary">South Africa: Constitutional Court</a></td></tr>
                    <tr><td><a href="/za/other/ZACCRolls" class="link-secondary">South Africa: Constitutional Court Rolls</a></td></tr>
                    <tr><td><a href="/za/cases/ZACCP" class="link-secondary">South Africa: Court of the Commissioner of Patents</a></td></tr>
                    <tr><td><a href="/za/cases/ZACOMMC" class="link-secondary">South Africa: Commercial Crime Court</a></td></tr>
                    <tr><td><a href="/za/journals/DEJURE" class="link-secondary">South Africa: <em>De Jure</em> Law Journal </a></td></tr>
                    <tr><td><a href="/za/journals/DEREBUS" class="link-secondary">South Africa: <em>DE REBUS</em>  </a></td></tr>
                    <tr><td><a href="/za/cases/ZAECBHC" class="link-secondary">South Africa: Eastern Cape High Court, Bhisho</a></td></tr>
                    <tr><td><a href="/za/other/ZAECBHCRolls" class="link-secondary">South Africa: Eastern Cape High Court Rolls, Bisho</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECGHC" class="link-secondary">South Africa: Eastern Cape High Court, Grahamstown</a></td></tr>
                    <tr><td><a href="/za/other/ZAECGHCRolls" class="link-secondary">South Africa: Eastern Cape High Court Rolls, Grahamstown</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECQBHC" class="link-secondary">South Africa: Eastern Cape High Court, Gqeberha</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECMKHC" class="link-secondary">South Africa: Eastern Cape High Court, Makhanda</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECMHC" class="link-secondary">South Africa: Eastern Cape High Court, Mthatha</a></td></tr>
                    <tr><td><a href="/za/other/ZAECMHCRolls" class="link-secondary">South Africa: Eastern Cape High Court Rolls, Mthatha</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECPEHC" class="link-secondary">South Africa: Eastern Cape High Court, Port Elizabeth</a></td></tr>
                    <tr><td><a href="/za/other/ZAECPEHCRolls" class="link-secondary">South Africa: Eastern Cape High Court Rolls, Port Elizabeth</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECELLC" class="link-secondary">South Africa: Eastern Cape High Court, East London Local Court</a></td></tr>
                    <tr><td><a href="/za/other/ZAECELLCRolls" class="link-secondary">South Africa: Eastern Cape High Court, East London Local Court Rolls</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAECPrGaz/" class="link-secondary">South Africa: Eastern Cape Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAEC" class="link-secondary">South Africa: Electoral Court </a></td></tr>
                    <tr><td><a href="/za/cases/ZAEQC" class="link-secondary">South Africa: Equality Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZAFSHC" class="link-secondary">South Africa: Free State High Court, Bloemfontein</a></td></tr>
                    <tr><td><a href="/za/other/ZAFSHCRolls" class="link-secondary">South Africa: Free State High Court Rolls, Bloemfontein</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAFSPrGaz/" class="link-secondary">South Africa: Free State Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAECHC" class="link-secondary">South Africa: High Courts - Eastern Cape</a></td></tr>
                    <tr><td><a href="/za/cases/ZAGPHC" class="link-secondary">South Africa: High Courts - Gauteng</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAGPPrGaz/" class="link-secondary">South Africa: Gauteng Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAKZHC" class="link-secondary">South Africa: High Courts - Kwazulu Natal</a></td></tr>
                    <tr><td><a href="/za/cases/ZAKZDHC" class="link-secondary">South Africa: Kwazulu-Natal High Court, Durban</a></td></tr>
                    <tr><td><a href="/za/other/ZAKZDHCRolls" class="link-secondary">South Africa: Kwazulu-Natal High Court Rolls, Durban</a></td></tr>
                    <tr><td><a href="/za/cases/ZAKZPHC" class="link-secondary">South Africa: Kwazulu-Natal High Court, Pietermaritzburg</a></td></tr>
                    <tr><td><a href="/za/other/ZAKZPHCRolls" class="link-secondary">South Africa: Kwazulu-Natal High Court Rolls, Pietermaritzburg</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAKZPrGaz/" class="link-secondary">South Africa: Kwazulu-Natal Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAIC" class="link-secondary">South Africa: Industrial Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZALAC" class="link-secondary">South Africa: Labour Appeal Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZALC" class="link-secondary">South Africa: Labour Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZALCCT" class="link-secondary">South Africa: Labour Court Cape Town </a></td></tr>
                    <tr><td><a href="/za/cases/ZALCJHB" class="link-secondary">South Africa: Labour Court Johannesburg </a></td></tr>
                    <tr><td><a href="/za/cases/ZALCPE" class="link-secondary">South Africa: Labour Court Port Elizabeth </a></td></tr>
                    <tr><td><a href="/za/cases/ZALCD" class="link-secondary">South Africa: Labour Court Durban </a></td></tr>
                    <tr><td><a href="/za/cases/ZALCC" class="link-secondary">South Africa: Land Claims Court</a></td></tr>
                    <tr><td><a href="/za/journals/LDD" class="link-secondary">South Africa: Law, Democracy and Development Law Journal</a></td></tr>
                    <tr><td><a href="/za/other/ZALRC" class="link-secondary">South Africa: Law Reform Commission</a></td></tr>
                    <tr><td><a href="/za/cases/ZALMPPHC" class="link-secondary">South Africa: Limpopo High Court, Polokwane</a></td></tr>
                    <tr><td><a href="/za/other/ZALMPPHCRolls" class="link-secondary">South Africa: Limpopo High Court Rolls, Polokwane</a></td></tr>
                    <tr><td><a href="/za/cases/ZALMPTHC" class="link-secondary">South Africa: Limpopo High Court, Thohoyandou</a></td></tr>
                    <tr><td><a href="/za/other/ZALMPHCRolls" class="link-secondary">South Africa: Limpopo High Court Rolls, Thohoyandou</a></td></tr>
                    <tr><td><a href="/za/gaz/ZALMPrGaz/" class="link-secondary">South Africa: Limpopo Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAMPMBHC/" class="link-secondary">South Africa: Mbombela High Court, Mpumalanga</a></td></tr>
                    <tr><td><a href="/za/cases/ZAMPMHC/" class="link-secondary">South Africa: Middelburg High Court, Mpumalanga</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAMPPrGaz/" class="link-secondary">South Africa: Mpumalanga Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZANCT" class="link-secondary">South Africa: National Consumer Tribunal</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAGovGaz/" class="link-secondary">South Africa: National Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZANCHC" class="link-secondary">South Africa: Northern Cape High Court, Kimberley</a></td></tr>
                    <tr><td><a href="/za/other/ZANCHCRolls" class="link-secondary">South Africa: Northern Cape High Court Rolls, Kimberley</a></td></tr>
                    <tr><td><a href="/za/gaz/ZANCPrGaz/" class="link-secondary">South Africa: Northern Cape Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/cases/ZAGPPHC" class="link-secondary">South Africa: North Gauteng High Court, Pretoria</a></td></tr>
                    <tr><td><a href="/za/other/ZAGPPHCRolls" class="link-secondary">South Africa: North Gauteng High Court Rolls, Pretoria</a></td></tr>
                    <tr><td><a href="/za/cases/ZANWHC" class="link-secondary">South Africa: North West Consumer Affairs Court, Mafikeng</a></td></tr>
                    <tr><td><a href="/za/cases/ZANWHC" class="link-secondary">South Africa: North West High Court, Mafikeng</a></td></tr>
                    <tr><td><a href="/za/other/ZANWHCRolls" class="link-secondary">South Africa: North West High Court Rolls, Mafikeng</a></td></tr>
                    <tr><td><a href="/za/gaz/ZANWPrGaz/" class="link-secondary">South Africa: North West Provincial Government Gazettes</a></td></tr>
                    <tr><td><a href="/za/journals/PER" class="link-secondary">South Africa: Potchefstroom Electronic Law Journal // Potchefstroomse Elektroniese Regsblad </a></td></tr>
                    <tr><td><a href="/za/other/ZARC" class="link-secondary">South Africa: Rules of Superior Courts</a></td></tr>
                    <tr><td><a href="/za/cases/ZARMC" class="link-secondary">South Africa: Rules of Magistrates Courts</a></td></tr>
                    <tr><td><a href="/za/cases/ZAGPJHC" class="link-secondary">South Africa: South Gauteng High Court, Johannesburg</a></td></tr>
                    <tr><td><a href="/za/other/ZAGPJHCRolls" class="link-secondary">South Africa: South Gauteng High Court Rolls, Johannesburg</a></td></tr>
                    <tr><td><a href="/za/cases/ZAST" class="link-secondary">South Africa: Special Tribunal</a></td></tr>
                    <tr><td><a href="/za/other/ZASTRolls" class="link-secondary">South Africa: Special Tribunal Court Rolls</a></td></tr>
                    <tr><td><a href="/za/cases/ZASCA" class="link-secondary">South Africa: Supreme Court of Appeal</a></td></tr>
                    <tr><td><a href="/za/other/ZASCARolls" class="link-secondary">South Africa: Supreme Court of Appeal Court Rolls</a></td></tr>
                    <tr><td><a href="/za/cases/ZATC" class="link-secondary">South Africa: Tax Court</a></td></tr>
                    <tr><td><a href="/za/cases/ZAWT" class="link-secondary">South Africa: Water Tribunal</a></td></tr>
                    <tr><td><a href="/za/cases/ZAWCHC" class="link-secondary">South Africa: Western Cape High Court, Cape Town</a></td></tr>
                    <tr><td><a href="/za/other/ZAWCHCRolls" class="link-secondary">South Africa: Western Cape High Court Rolls, Cape Town</a></td></tr>
                    <tr><td><a href="/za/gaz/ZAWCPrGaz/" class="link-secondary">South Africa: Western Cape Provincial Government Gazettes</a></td></tr>
                    </tbody>
                  </table>
                </div>
              
3. Folgt man einem Link (z.B.: https://www.saflii.org/za/cases/ZAWCHC/), so findet man eine Übersichtsseite mit nach einzelnen Jahren sortierten Schriftstücken. Die Links liegen in einfacher form vor (XPATH: /html/body/div/div/div[2]/div/div/div/div/table/tbody/tr/td/h3[2]/a[1] ). Aus der URL `https://www.saflii.org/za/cases/ZAWCHC/` wird dann `https://www.saflii.org/za/cases/ZAWCHC/2023/` und so weiter für jedes Jahr. 


<br><br>
<a href="1993/">1993</a>
<a href="1994/">1994</a>
<a href="1995/">1995</a>
<a href="1996/">1996</a>
<a href="1997/">1997</a>
<a href="1998/">1998</a>
<a href="1999/">1999</a>
<a href="2000/">2000</a>
<a href="2001/">2001</a>
<a href="2002/">2002</a>
<a href="2003/">2003</a>
<a href="2004/">2004</a>
<a href="2005/">2005</a>
<a href="2006/">2006</a>
<a href="2007/">2007</a>
<a href="2008/">2008</a>
<a href="2009/">2009</a>
<a href="2010/">2010</a>
<a href="2011/">2011</a>
<a href="2012/">2012</a>
<a href="2013/">2013</a>
<a href="2014/">2014</a>
<a href="2015/">2015</a>
<a href="2016/">2016</a>
<a href="2017/">2017</a>
<a href="2018/">2018</a>
<a href="2019/">2019</a>
<a href="2020/">2020</a>
<a href="2021/">2021</a>
<a href="2022/">2022</a>
<a href="2023/">2023</a>
<a href="2024/">2024</a>
<a href="2025/">2025</a>

4. Folgt man nun einem Link zu einem Jahr (z.B.: https://www.saflii.org/za/cases/ZAWCHC/2023/), so findet man dort alle Schriftstücke des jeweiligen Jahres. Diese sind in der Regel nach Jahr und Monat sortiert. Die Links zu den einzelnen Schriftstücken sind in der Form `https://www.saflii.org/za/cases/ZAWCHC/2023/1.html` aufgebaut (XPATH: /html/body/div/div/div[2]/div/div/div/div/table/tbody/tr/td/ul[2]/li[1]/a). Dabei ist `ZAWCHC` das Gericht, `2023` das Jahr und `1` die Nummer des Schriftstücks.


#### Databases

https://www.saflii.org/za/journals/ADRY
https://www.saflii.org/za/journals/AHRLJ
https://www.saflii.org/za/journals/ALR
https://www.saflii.org/za/cases/ZACAC
https://www.saflii.org/za/cases/ZACT
https://www.saflii.org/za/cases/ZACONAF
https://www.saflii.org/za/cases/ZACGSO
https://www.saflii.org/za/cases/ZACC
https://www.saflii.org/za/other/ZACCRolls
https://www.saflii.org/za/cases/ZACCP
https://www.saflii.org/za/cases/ZACOMMC
https://www.saflii.org/za/journals/DEJURE
https://www.saflii.org/za/journals/DEREBUS
https://www.saflii.org/za/cases/ZAECBHC
https://www.saflii.org/za/other/ZAECBHCRolls
https://www.saflii.org/za/cases/ZAECGHC
https://www.saflii.org/za/other/ZAECGHCRolls
https://www.saflii.org/za/cases/ZAECQBHC
https://www.saflii.org/za/cases/ZAECMKHC
https://www.saflii.org/za/cases/ZAECMHC
https://www.saflii.org/za/other/ZAECMHCRolls
https://www.saflii.org/za/cases/ZAECPEHC
https://www.saflii.org/za/other/ZAECPEHCRolls
https://www.saflii.org/za/cases/ZAECELLC
https://www.saflii.org/za/other/ZAECELLCRolls
https://www.saflii.org/za/gaz/ZAECPrGaz/
https://www.saflii.org/za/cases/ZAEC
https://www.saflii.org/za/cases/ZAEQC
https://www.saflii.org/za/cases/ZAFSHC
https://www.saflii.org/za/other/ZAFSHCRolls
https://www.saflii.org/za/gaz/ZAFSPrGaz/
https://www.saflii.org/za/cases/ZAECHC
https://www.saflii.org/za/cases/ZAGPHC
https://www.saflii.org/za/gaz/ZAGPPrGaz/
https://www.saflii.org/za/cases/ZAKZHC
https://www.saflii.org/za/cases/ZAKZDHC
https://www.saflii.org/za/other/ZAKZDHCRolls
https://www.saflii.org/za/cases/ZAKZPHC
https://www.saflii.org/za/other/ZAKZPHCRolls
https://www.saflii.org/za/gaz/ZAKZPrGaz/
https://www.saflii.org/za/cases/ZAIC
https://www.saflii.org/za/cases/ZALAC
https://www.saflii.org/za/cases/ZALC
https://www.saflii.org/za/cases/ZALCCT
https://www.saflii.org/za/cases/ZALCJHB
https://www.saflii.org/za/cases/ZALCPE
https://www.saflii.org/za/cases/ZALCD
https://www.saflii.org/za/cases/ZALCC
https://www.saflii.org/za/journals/LDD
https://www.saflii.org/za/other/ZALRC
https://www.saflii.org/za/cases/ZALMPPHC
https://www.saflii.org/za/other/ZALMPPHCRolls
https://www.saflii.org/za/cases/ZALMPTHC
https://www.saflii.org/za/other/ZALMPHCRolls
https://www.saflii.org/za/gaz/ZALMPrGaz/
https://www.saflii.org/za/cases/ZAMPMBHC/
https://www.saflii.org/za/cases/ZAMPMHC/
https://www.saflii.org/za/gaz/ZAMPPrGaz/
https://www.saflii.org/za/cases/ZANCT
https://www.saflii.org/za/gaz/ZAGovGaz/
https://www.saflii.org/za/cases/ZANCHC
https://www.saflii.org/za/other/ZANCHCRolls
https://www.saflii.org/za/gaz/ZANCPrGaz/
https://www.saflii.org/za/cases/ZAGPPHC
https://www.saflii.org/za/other/ZAGPPHCRolls
https://www.saflii.org/za/cases/ZANWHC
https://www.saflii.org/za/cases/ZANWHC
https://www.saflii.org/za/other/ZANWHCRolls
https://www.saflii.org/za/gaz/ZANWPrGaz/
https://www.saflii.org/za/journals/PER
https://www.saflii.org/za/other/ZARC
https://www.saflii.org/za/cases/ZARMC
https://www.saflii.org/za/cases/ZAGPJHC
https://www.saflii.org/za/other/ZAGPJHCRolls
https://www.saflii.org/za/cases/ZAST
https://www.saflii.org/za/other/ZASTRolls
https://www.saflii.org/za/cases/ZASCA
https://www.saflii.org/za/other/ZASCARolls
https://www.saflii.org/za/cases/ZATC
https://www.saflii.org/za/cases/ZAWT
https://www.saflii.org/za/cases/ZAWCHC
https://www.saflii.org/za/other/ZAWCHCRolls
https://www.saflii.org/za/gaz/ZAWCPrGaz/

