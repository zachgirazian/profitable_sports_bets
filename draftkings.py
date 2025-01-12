from playwright.sync_api import sync_playwright
from selectolax.parser import HTMLParser
from pdb import set_trace as stop

# Get the game line data
def game_line(content):
    print('Game line scraping started')
    html = HTMLParser(content)
    markets = html.css('div.rj-market')
    print('Alternate Run Line')
    label = markets[1].css('p.rj-market__label')
    arl_bets = markets[1].css('button.rj-market__button')
    atr_bets = markets[2].css('button.rj-market__button')
    team_a = []
    team_b = []
    over = []
    under = []
    team_1 = label[0].text()
    print(team_1)
    for bet in arl_bets[0::2]:
        arl_t1 = {
            'title':bet.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': bet.css_first('span.rj-market__button-yourbet-odds').text()
        }
        print(arl_t1)
        team_a.append(arl_t1)
    team_2 = label[1].text()
    print(team_2)
    for bet in arl_bets[1::2]:
        arl_t2 = {
            'title':bet.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': bet.css_first('span.rj-market__button-yourbet-odds').text()
        }
        print(arl_t2)
        team_b.append(arl_t2)
    arl = {
        team_1: team_a,
        team_2 : team_b
    }
    print('Alternate Total Runs')
    print('Over')
    for bet in atr_bets[0::2]:
        atr_over = {
            'title':bet.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': bet.css_first('span.rj-market__button-yourbet-odds').text()
        }
        print(atr_over)
        over.append(atr_over)
    print('Under')
    for bet in atr_bets[1::2]:
        atr_under = {
            'title':bet.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': bet.css_first('span.rj-market__button-yourbet-odds').text()
        }
        print(atr_under)
        under.append(atr_under)
    atr = {
        'over': over,
        'under': under
    }
    game_ln = [arl, atr]
    print('Game line scrape finished!')
    return game_ln

# Get the hits tab data
def hits(content):
    html = HTMLParser(content)
    markets = html.css('div.rj-market')
    extra_header = markets[0].css_first('p.rj-market__tooltip-web-text').text()
    odd_header = markets[0].css_first('h2.rj-market__header').text().replace(extra_header,'')
    print(f'{odd_header} scraping started')
    plgh_bets = markets[0].css('button.rj-market__button')
    player_hits = []
    for bet in plgh_bets:
        card = {
            'name':bet.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': bet.css_first('span.rj-market__button-yourbet-odds').text()
        }
        print(card)
        player_hits.append(card)
    return player_hits

# Get the pitcher_props tab data
def pitcher_props(content):
    print('Pitcher Props scraping started')
    html = HTMLParser(content)
    markets = html.css('div.rj-market')
    pitch_props = []
    for market in markets:
        extra_header = market.css_first('p.rj-market__tooltip-web-text').text()
        odd_header = market.css_first('h2.rj-market__header').text().replace(extra_header,'')
        odd_line = []
        
        odds = market.css('button.rj-market__button')
        for odd in odds:
            card = {
            'title':odd.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': odd.css_first('span.rj-market__button-yourbet-odds').text()
            }
            odd_line.append(card)
            print(card)
        mark = {
            'odd_header': odd_header,
            'odd_line': odd_line
        }
        pitch_props.append(mark)
    print('Pitcher Props scraping finished!')
    return pitch_props

# Get the rbis tab data
def rbis_tab(content):
    html = HTMLParser(content)
    markets = html.css('div.rj-market')
    rbis_list = []
    for market in markets:
        extra_header = market.css_first('p.rj-market__tooltip-web-text').text()
        odd_header = market.css_first('h2.rj-market__header').text().replace(extra_header,'')
        print(odd_header)
        odd_line = []
        odds = market.css('button.rj-market__button')
        for odd in odds:
            card = {
            'title':odd.css_first('span.rj-market__button-yourbet-title').text(),
            'odds': odd.css_first('span.rj-market__button-yourbet-odds').text()
            }
            odd_line.append(card)
            print(card)
        mark = {
            'odd_header': odd_header,
            'odd_line': odd_line
        }
        rbis_list.append(mark)
    return rbis_list

# Get the main odds data
def top_bet(content):
    html = HTMLParser(content)
    data = []
    markets = html.css('div.rj-market')
    groups = markets[0].css('button.rj-market__button')
    odds = {}
    odd_1 = {'title': groups[0].css_first('span.rj-market__button-yourbet-title').text(), 'odd': groups[0].css_first('span.rj-market__button-yourbet-odds').text()}
    odd_2 = {'title': groups[4].css_first('span.rj-market__button-yourbet-title').text(), 'odd': groups[4].css_first('span.rj-market__button-yourbet-odds').text()}
    odds['odd_1'] = odd_1
    odds['odd_2'] = odd_2
    data.append(odds)
    return data


def get_data(url):
    data = {}
    with sync_playwright() as p:
        proxy = {
            "server": 'server',
            'username': 'username',
            'password': 'password'
        }
        browser = p.chromium.launch(headless=False ,proxy=proxy)
        context = browser.new_context()
        page = context.new_page()
        page.set_viewport_size({"width": 1900, "height": 880})
        page.set_default_timeout(0)
        print('Page loading...')
        page.goto(url)
        selector = 'button.rj-market__group'
        content_selector = 'div.rj-market__lazy-render-container'
        page.wait_for_selector(selector, timeout=0)
        groups = page.query_selector_all(selector)
        
        # Get top bet and run top_bet function
        content = page.inner_html(content_selector)
        main_bet = top_bet(content)
        
        # Click the top bet and get combined odd
        bet_selector = 'button.rj-market__button'
        bet_elements = page.query_selector_all(bet_selector)
        bet_elements[4].click()
        page.wait_for_selector('button.rj-market__button--selected', timeout=0)
        bet_elements[0].click()
        page.wait_for_selector('button.rj-market__button--selected', timeout=0)
        combined_selector = 'div.betslip-odds__display-standard span'
        combined_odds = {'combined_odds':page.inner_text(combined_selector)}
        main_bet.append(combined_odds)
        data['main_bet'] = main_bet
        
        # Click game line tab and run game_line function
        groups[2].click()
        content = page.inner_html(content_selector)
        game_ln = game_line(content)
        data['game_line'] = game_ln
        page.wait_for_timeout(2000)
        
        # Click Hits tab and run hits function
        groups[3].click()
        content = page.inner_html(content_selector)
        hits_tab = hits(content)
        data['hits'] = hits_tab
        page.wait_for_timeout(2000)
        
        # Click pitcher_props tab and run pitcher_props function
        groups[4].click()
        content = page.inner_html(content_selector)
        pitcher_tab = pitcher_props(content)
        data['pitcher_props'] = pitcher_tab
        page.wait_for_timeout(2000)
        
        # Click HOME RUN tab and run hits function
        groups[5].click()
        content = page.inner_html(content_selector)
        home_run = hits(content)
        data['home_runs'] = home_run
        page.wait_for_timeout(2000)
        
        # Click RBIS tab and run rbis_tab function
        groups[6].click()
        content = page.inner_html(content_selector)
        rbis = rbis_tab(content)
        data['rbis'] = rbis
        page.wait_for_timeout(2000)
        
        # Click total bases tab and run rbis_tab function
        groups[7].click()
        content = page.inner_html(content_selector)
        total_bases = rbis_tab(content)
        data['total_bases'] = total_bases
        page.wait_for_timeout(2000)
        
        
        browser.close()
    return data


def main():
    url = 'https://sportsbook.draftkings.com/event/stl-cardinals-%40-was-nationals/29034651?sgpmode=true'
    data = get_data(url) # All data here in this dictionary


if __name__ == "__main__":
    main()