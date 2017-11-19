import re
import glob
import csv
import urllib.request
import lxml.html as lh


def get_sets_from_year(setsfile):
    '''Returns list of (set_id, variant) given a .csv file with set information
    data from the brickset.com webpage.'''

    with open(setsfile) as sf:
        return [(int(line[1]), int(line[2])) for line in csv.reader(sf)
                if (re.match('[0-9]+', line[1])
                    and re.match('[0-9]+', line[2])
                    and 'Minifigures' not in line[3])]


def parse_infobox(el_list):
    '''Takes the first div.featurebox from the brickset.com set page and
    parses it to retrieve information about the set (name, # of pieces, etc.).
    The info is stored in a series of dt and dd tags. Upon meeting a dt tag,
    the dd's are collected in to a list. When a new dt is met, the previous
    dt:  [dd's] is combination is stored. Returns the data as dictionary.'''

    infobox = dict()
    key = ''
    values = []
    for el in el_list[1:-1]:
        if el.tag == 'dt':
            # Discard unnecessary info
            if (key not in ['', 'Current value', 'Price per piece',
                            'Barcodes', 'Notes', 'LEGO item numbers']
                    and values != []):
                # Turn a list of values from several dd's into a string
                infobox[key] = ','.join(values)
            key = el.text
            values = []
        elif el.tag == 'dd':
            # Some fields contain the information in a link
            if (key in ['Theme', 'Subtheme', 'Year released', 'Pieces', 'Minifigs']
                and el.xpath('a') != []):
                values.append(el.xpath('a')[0].text)
            elif key == 'Tags' and len(el.xpath('span/a')) >= 0:
                # Some fields are list of links
                for a in el.xpath('span/a'):
                    values.append(a.text)
            else:
                values.append(el.text)
    return infobox


def parse_price_guide(pg_table):
    '''Takes the first table.pcipgInnerTable and parses it to retrieve the
    monthly summary price data. The data are returned as:
    {month: [stats]}.'''

    # Splits the string by months
    pat = re.compile(
        '((?:January|February|March|April|May|June|July|August|September|October|November|December) (?:[0-9]{4}))')
    split_text = re.split(pat, re.sub('\s+', ' ', pg_table.text_content()))
    month_label_positions = [i for i, v in enumerate(split_text)
                             if re.match(pat, v)]

    def split_summary_fields(fields_text):
        # The summary stats are in the form:
        # (Field Name: (USD)? Number)
        pat = re.compile(
            '(?:([\sa-zA-Z]+):(?:[A-Z]+\s\$)?([.0-9]+)\s?)')
        matches = list(filter(None, re.split(pat, fields_text)))
        return dict(zip(matches[0::2], matches[1::2]))

    monthly_data = dict()
    for pos in month_label_positions:
        # The following removes the single transaction data that precede the
        # summary statistics (Total Lots is the first sum. stat. field).
        summary_fields = ''.join(
            str(i) for i in split_text[pos + 1].partition('Total Lots:')[1:3])
        monthly_data[split_text[pos]] = split_summary_fields(
            summary_fields)

    return monthly_data


sample_files = glob.glob('./sample pages/*.html')

with open('sets_2012_info.csv', 'w', newline='') as info_csv, \
     open('sets_2012_prices.csv', 'w', newline='') as prices_csv:

    info_fields = ['Set number', 'Name', 'Set type', 'Theme group', 'Theme',
                   'Subtheme', 'Year released', 'Tags', 'Dimensions', 'Weight',
                   'Pieces', 'Minifigs', 'RRP', 'Age range', 'Packaging',
                   'Availability']
    prices_fields = ['Set number', 'Name', 'Year', 'Month', 'Total Lots',
                     'Total Qty', 'Min Price', 'Avg Price', 'Qty Avg Price',
                     'Max Price']

    info_csv_writer = csv.DictWriter(info_csv, fieldnames=info_fields, delimiter=';')
    info_csv_writer.writeheader()

    prices_csv_writer = csv.DictWriter(prices_csv, fieldnames=prices_fields, delimiter=';')
    prices_csv_writer.writeheader()

    sets_2012 = get_sets_from_year('sets_2012.csv')
    sets_not_found = []

    for (lego_id, variant) in sets_2012:
        print('Scraping LEGO set: {}-{}'.format(lego_id, variant))
        brickset_page = lh.parse(urllib.request.urlopen(
            'https://brickset.com/sets/' + '{}-{}'.format(lego_id, variant)))
        bricklink_page = lh.parse(urllib.request.urlopen(
            'https://www.bricklink.com/v2/catalog/catalogitem_pgtab.page?S='
            + '{}-{}'.format(lego_id, variant)
            + '&st=2&gm=1&gc=0&ei=0&prec=1&showflag=0&showbulk=0&currency=1'))

        try:
            # Retrieve the relevant parts of HTML
            infobox_els = brickset_page.xpath('//dl[dt="Set number"]')[0]
            pg_els = bricklink_page.xpath('//table[@class="pcipgInnerTable"]')[0]
        except IndexError:
            # Some sets have mismatched set ids on bricklink and brickset
            # Some sets are also not found if the # of requests exceeds the
            # quota on the bricklink website. The quota is prob. >100 & <500.
            sets_not_found.append('{}-{}'.format(lego_id, variant))
            pass
        else:
            infobox = parse_infobox(infobox_els)
            price_guide = parse_price_guide(pg_els)

            info_csv_writer.writerow({**{'Set number': lego_id}, **infobox})

            for date, price_summary in price_guide.items():
                month, year = date.split(' ')
                data = {**{'Set number': lego_id, 'Month': month, 'Year': year},
                        **{'Name': infobox['Name']},
                        **price_summary}
                prices_csv_writer.writerow(data)

    print('{} LEGOs not found: {}'.format(len(sets_not_found), ', '.join(sets_not_found)))
