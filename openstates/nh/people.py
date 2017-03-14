import re
import lxml.html

from pupa.scrape import Person, Scraper

class NHPersonScraper(Scraper):
    jurisdiction = 'nh'
    latest_only = True
    members_url = 'http://www.gencourt.state.nh.us/downloads/Members.txt'
    lookup_url = 'http://www.gencourt.state.nh.us/house/members/memberlookup.aspx'
    house_profile_url = 'http://www.gencourt.state.nh.us/house/members/member.aspx?member={}'
    senate_profile_url = 'http://www.gencourt.state.nh.us/Senate/members/webpages/district{}.aspx'

    chamber_map = {'H': 'lower', 'S': 'upper'}
    party_map = {
        'D': 'Democratic',
        'R': 'Republican',
        'I': 'Independent',
        'L': 'Libertarian',
    }

    def scrape(self, chamber=None):
        if chamber:
            yield from self.scrape_chamber(chamber)
        else:
            yield from self.scrape_chamber('upper')
            yield from self.scrape_chamber('lower')

    def scrape_chamber(self, chamber):
        # seat_map = self._parse_seat_map()
        seat_map = {}
        for row in self._parse_members_txt():
           #print(chamber)
           # print(self.chamber_map[row['LegislativeBody']])
            if self.chamber_map[row['LegislativeBody']] == chamber:
                print("MATCH")
                legislator = self._parse_legislator(row, chamber, seat_map, self.members_url)
                #self.save_legislator(leg)
                yield legislator

    def _get_photo(self, url, chamber):
        """Attempts to find a portrait in the given legislator profile."""
        doc = self.lxmlize(url)

        if chamber == 'upper':
            src = doc.xpath('//div[@id="page_content"]//img[contains(@src, '
                '"images/senators") or contains(@src, "Senator")]/@src')
        elif chamber == 'lower':
            src = doc.xpath('//img[contains(@src, "images/memberpics")]/@src')

        if src and 'nophoto' not in src[0]:
            photo_url = src[0]
        else:
            photo_url = ''

        return photo_url

    def _parse_legislator(self, row, chamber, seat_map, members_url):
        print("parsing leg")
        # Capture legislator vitals.
        first_name = row['FirstName']
        middle_name = row['MiddleName']
        last_name = row['LastName']
        full_name = '{} {} {}'.format(first_name, middle_name, last_name)
        full_name = re.sub(r'[\s]{2,}', ' ', full_name)

        district = '{} {}'.format(row['County'], int(row['District'])).strip()

        print(district)

        party = self.party_map[row['party'].upper()]
        email = row['WorkEmail']

        extras = {'middle_name':middle_name,
                  'first_name':first_name,
                  'last_name':last_name
                  }

        legislator = Person(primary_org=chamber,
                            district=district,
                            name=full_name,
                            party=party,
                            role="legislator")

        if email:
            contact_details = [{'type': 'email',
                            'value': email,
                            'note': '',
                            'label': 'email'
                            }]
            
            legislator.contact_details=contact_details

        legislator.extras = extras

        legislator.add_source(self.members_url)

        # # Capture legislator office contact information.
        # district_address = '{}\n{}\n{}, {} {}'.format(row['Address'],
        #     row['address2'], row['city'], row['State'], row['Zipcode']).strip()

        # phone = row['Phone'].strip()
        # if not phone:
        #     phone = None

        # legislator.add_office('district', 'Home Address',
        #                       address=district_address,
        #                       phone=phone)

        print( legislator)

        # # Retrieve legislator portrait.
        # profile_url = None
        # if chamber == 'upper':
        #     profile_url = self.senate_profile_url.format(row['District'])
        # elif chamber == 'lower':
        #     try:
        #         seat_number = seat_map[row['seatno']]
        #         profile_url = self.house_profile_url.format(seat_number)
        #     except KeyError:
        #         pass

        # if profile_url:
        #     legislator['photo_url'] = self._get_photo(profile_url, chamber)
        #     legislator.add_source(profile_url)

        return legislator

    def _parse_members_txt(self):
        lines = self.get(self.members_url).text.splitlines()

        header = lines[0].split('\t')

        for line in lines[1:]:
            yield dict(zip(header, line.split('\t')))

    def _parse_seat_map(self):
        """Get mapping between seat numbers and legislator identifiers."""
        seat_map = {}
        page = self.lxmlize(self.lookup_url)
        options = page.xpath('//select[@id="member"]/option')
        for option in options:
            member_url = self.house_profile_url.format(option.attrib['value'])
            member_page = self.lxmlize(member_url)
            table = member_page.xpath('//table[@id="Table1"]')
            if table:
                res = re.search(r'seat #:(\d+)', table[0].text_content(), re.IGNORECASE)
                if res:
                    seat_map[res.groups()[0]] = option.attrib['value']
        return seat_map

    def lxmlize(self, url):
        doc = self.get(url).content
        doc = lxml.html.fromstring(doc)
        return doc