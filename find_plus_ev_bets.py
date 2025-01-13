import requests
import numpy as np
from datetime import datetime
import sys
import pandas as pd
sys.path.append("path_here")
from difflib import SequenceMatcher
import odds_toolbox as tb
from astropy.time import Time
from datetime import datetime, timedelta
import pygsheets
from pdb import set_trace as stop
import pickle
import matplotlib.pylab as plt
api_key = 'api_key'

# Load pickle file
def load_pickle(filename):
    with open(filename, 'rb') as f: dict = pickle.load(f)
    return dict 

# Save pickle file
def save_pickle(stuff,filename):
    with open(filename, 'wb') as f: 
        pickle.dump(stuff, f)

# Check if two strings are similar - good for matching team names like "Atlanta united FC" and "Atlanta Utd"
def similar_strings(a, b):
    result = []
    for b1 in b:
        result.append(SequenceMatcher(None, a, b1).ratio())
    return result

# Convert american odds to decimal odds
def american_to_dec(odd):
    if odd <= -100:
        decodd = 1 - 100/odd
    else:
        decodd = 1 + odd/100
    return decodd
        
# Given the odds and  thetakeback, calculate the fair odds
def fair_odds(dec_odd_1,dec_odd_2,dec_odd_3=-99):
    #implied prob (%)
    imp_1 = 1.0/dec_odd_1
    imp_2 = 1.0/dec_odd_2
    imp_3 = 1.0/dec_odd_3
    
    #Fair probability (%)
    if dec_odd_3 < 0: # 2-way devig
        prob_1 = imp_1/(imp_1 + imp_2)
        prob_2 = imp_2/(imp_1 + imp_2)
        prob_3 = -99
    else:
        prob_1 = imp_1/(imp_1 + imp_2 + imp_3)
        prob_2 = imp_2/(imp_1 + imp_2 + imp_3)
        prob_3 = imp_3/(imp_1 + imp_2 + imp_3)

    #Fair odds
    fair_1 = 1.0/prob_1
    fair_2 = 1.0/prob_2
    fair_3 = 1.0/prob_3
    
    if dec_odd_3 < 0: # 2-way devig
        return fair_1, fair_2
    else: # 3-way devig
        return fair_1, fair_2, fair_3
    
# Calculate average odds or fair odds for a single bet
def calc_stuff(array_1,array_2,array_3=['',-1]):
    # Average
    # input arrays may have blank entries that need to be removed before averaging
    avg_1 = np.mean([a1 for a1 in array_1 if a1]) # this will average all array elements but ignore blank '' entries
    avg_2 = np.mean([a1 for a1 in array_2 if a1])
    avg_3 = np.mean([a1 for a1 in array_3 if a1])
    
    # Fair
    if avg_3 < 0: #2-way devig
        fair_1, fair_2 = fair_odds(avg_1,avg_2) # calc fair odds based on averages        ##** Explore different strategies for this!!*****
    else:         # 3-way devig
        fair_1, fair_2, fair_3 = fair_odds(avg_1,avg_2,dec_odd_3=avg_3)
    
    # return format is 
    # average first input, average second input, fair first input, fair second input
    if avg_3 < 0: #2-way devig
        return np.round(avg_1,2), np.round(avg_2,2), np.round(fair_1,2), np.round(fair_2,2), '', ''
    else: # 3-way devig
        return np.round(avg_1,2), np.round(avg_2,2), np.round(avg_3,2), np.round(fair_1,2), np.round(fair_2,2), np.round(fair_3,2)
    
# Calculate average and fair odds for player prop dictionary
def calc_stuff_player_prop(dict):
    for player in dict:
        for bet in dict[player]:
            for point in dict[player][bet]:
                #try:
                over_hold = dict[player][bet][point]['over'][2:]                    
                under_hold = dict[player][bet][point]['under'][2:]
                
                # Get rid of NaNs and store in master dict
                avg1, avg2, f1, f2, dummy1, dummy2 = calc_stuff(over_hold,under_hold)
                arr = [avg1, avg2, f1, f2]
                for kkk, a1 in enumerate(arr):
                    if not np.isfinite(a1):
                        arr[kkk] = ''
                dict[player][bet][point]['over'][0] = arr[0]
                dict[player][bet][point]['under'][0] = arr[1]
                dict[player][bet][point]['over'][1] = arr[2]
                dict[player][bet][point]['under'][1] = arr[3]
                 
# Get odds by request to oddsAPI 
def get_odds(sport,markets,dict,eventId=None,prop=False):
    
    for market in markets:
        
        #for region in ['us','uk','eu','us2']:
        for region in ['us']:
            
            # Set parameters for request
            params={
            'api_key': api_key,
            'regions': region,
            'oddsFormat': 'decimal',
            'dateFormat': 'iso',
            'sport': sport,
            'markets': market,
            }
            
            # If a player prop, need eventId to target a single game
            params['eventIds'] = eventId
                
            # Shoot request to oddsAPI
            if prop:
                odds_response = requests.get(f'https://api.the-odds-api.com/v4/sports/' + sport + '/events/' + eventId + '/odds', params=params)
            else:
                odds_response = requests.get(f'https://api.the-odds-api.com/v4/sports/' + sport + '/odds', params=params)
        
            # check if successful connection
            if odds_response.status_code != 200:
                print(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.text}')
                return 
      
            # Parse and Extract odds into master dictionary
            if not prop:
                parse_odds(odds_response.json(),market,dict)
                
            if prop:
                # Parse odds and store in master dict
                parse_odds_player_prop(odds_response.json(),market,props_dict)

            # Check the usage quota
            print('Remaining requests', odds_response.headers['x-requests-remaining'])
            print('Used requests', odds_response.headers['x-requests-used'])
            
          
            # save odds for debug parsing
            #np.save(odds_filename,odds_json)
            #save_pickle(odds_json,'mlb_prop_test.pickle')

# return list of eventIds for a single sport - only for today's games (unless tomorrow_okay=True) that are not live
def get_eventIds(sport,tomorrow_okay=False):
    
    # Set parameters for request
    params={
    'api_key': api_key,
    'regions': 'us',
    'oddsFormat': 'decimal',
    'dateFormat': 'iso',
    'sport': sport,
    'markets': 'h2h',
    }
    
    odds_response = requests.get(f'https://api.the-odds-api.com/v4/sports/' + sport + '/odds', params=params)

    # check if successful connection
    if odds_response.status_code != 200:
        print(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.text}')
        return 
    
    # oddsAPI call to get event Ids
    stuff = odds_response.json()

    # loop through games and extract eventIds
    # check if game has already started - don't want live odds
    eventIds = []
    for game1 in stuff:
        thedate = Time(game1['commence_time'].split('Z')[0]).datetime
        if (thedate) < (datetime.today() + timedelta(hours=1)): # game already started/
            continue
        
        # Check if game tomorrow - if so then skip unless allowed by tomorrow_okay keyword
        if not tomorrow_okay:
            now  = datetime.now()
            
            # if last day of month then this will break (cant have June 32 for example) use try except to get around it
            try:
                if thedate > datetime(now.year,now.month,now.day+1):
                    continue
            except:
                if thedate > datetime(now.year,now.month +1,1):
                    continue

        eventIds.append(game1['id'])
        
    return eventIds

# Parse h2h (moneyline), spread, or totals lines
def parse_odds(odds,market,dict):

    # loop through each game and extract odds
    for game in odds: 
        
        # Time Check of game (don't want games already started or tomorrow)
        if False:
            # check if game has already started - don't want live odds
            thedate = Time(game['commence_time'].split('Z')[0]).datetime
            if (thedate) < (datetime.today() + timedelta(hours=1)): continue
            # Check if game tomorrow - if so then skip
            #now  = datetime.now()
            #if thedate > datetime(now.year,now.month,now.day+1): continue
        
        # Master dictionary key for this game, format is ("Away Team-Home Team")
        index = game['away_team'] + '-' + game['home_team']

        # Check if game already in master dict, if not then add it
        temp = [''] * (len(sportsbook_order) + 2)     # add 2 for average/fair odds
        if index not in dict:
            # Arrays correct size to hold odds from each chosen sportsbook and average/fair odds
            dict[index] = {'h2h': {'away':temp.copy(), 'home':temp.copy(), 'draw':temp.copy()}, 'spreads': {}, 'totals': {}}        # initiate dictionary of correct structure
        
        # loop through sportsbooks and extract odds for the single game
        for book in game['bookmakers']:

            # if book not in wanted list then skip
            #print (book['key'])
            if book['key'] not in sportsbook_order: continue
            
            # Check if odds are old - use "last update" to get time last odds were acquired                ******* Need to add this feature ********
            # book['markets'][0]['last_update']
        
            # Store odds in master dictionary 
            # Moneyline and spread/total have diff structure
            for odds1 in book['markets'][0]['outcomes']:
               
               # Moneyline
                if market == 'h2h':
                    if odds1['name'] == game['away_team']:
                        dict[index]['h2h']['away'][sportsbook_order.index(book['key'])] =  odds1['price']
                    if odds1['name'] == game['home_team']:
                        dict[index]['h2h']['home'][sportsbook_order.index(book['key'])] =  odds1['price']
                    if odds1['name'] == 'Draw':
                        dict[index]['h2h']['draw'][sportsbook_order.index(book['key'])] =  odds1['price']  
                else:
                    # Totals
                    if market =='totals':
                        # Check if bet already in master dict, if not then add it
                        if odds1['point'] not in dict[index][market]:
                            dict[index][market][odds1['point']] = {'over':temp.copy(),'under':temp.copy()}
                        
                        # Add to master dictionary
                        if odds1['name'] == 'Over':
                            dict[index][market][odds1['point']]['over'][sportsbook_order.index(book['key'])] = odds1['price']
                        if odds1['name'] == 'Under':
                            dict[index][market][odds1['point']]['under'][sportsbook_order.index(book['key'])] = odds1['price']
                    
                    # Spreads       
                    if market =='spreads':
                        # Get correct dict key (home or away)
                        if odds1['name'] == game['home_team']:
                            lab = 'home'
                        elif odds1['name'] == game['away_team']:
                            lab = 'away'
                        else:
                            print('\n \n not matching home or away team names!!! \n \n')
                   
                   
                        # Check if bet already in master dict, if not then add it
                        if odds1['point'] not in dict[index][market]:
                            dict[index][market][odds1['point']] = {}
                        
                        # Add to master dictionary
                        dict[index][market][odds1['point']][lab] = temp.copy()
                        dict[index][market][odds1['point']][lab][sportsbook_order.index(book['key'])] = odds1['price']

    
    # Calculate average and fair odds and store them in master dictionary
    for game in dict:
        for bet in dict[game][market]:
            
            # Moneyline
            if market == 'h2h': # moneyline
     
                # Choose dict element I am using
                dict_element = dict[game][market]
                            
                # Sometimes there is a game with all empty odds for some reason - skip if so
                if not any(dict_element['away']): continue
                
                # Check if 3-way moneyline or not
                array_3 = dict_element['draw']
                if not any(dict[game][market]['draw']):
                    array_3 = ['',-1]
                
                # Calc average and fair odds
                if array_3 == ['',-1]: # no draw line
                    dict_element['away'][0], dict_element['home'][0], dict_element['away'][1], dict_element['home'][1], a1, a2 = calc_stuff(dict_element['away'],dict_element['home'],array_3=array_3)
                else: #draw line (soccer etc.)
                    dict_element['away'][0], dict_element['home'][0], dict_element['draw'][0], dict_element['away'][1], dict_element['home'][1], dict_element['draw'][1] = calc_stuff(dict_element['away'],dict_element['home'],array_3=array_3)
                
                # If no draw then force to be blank
                #if array_3 == ['',-1]:
                #    dict_element['draw'][0] = ""
                #    dict_element['draw'][1] = ""
                
            # Totals
            if market == 'totals':  
                # Choose dict element I am using
                dict_element = dict[game][market][bet]
                
                # Calc average and fair odds
                dict_element['over'][0], dict_element['under'][0],dict_element['over'][1], dict_element['under'][1], a1, a2 = calc_stuff(dict_element['over'],dict_element['under'])            
            
            # Spreads
            if market == 'spreads': 
                
                dict_element = dict[game][market][bet]
                
                # List of keys
                keys_list = list(dict_element.keys())
                
                # Choose dict element I am using
                dict_element = dict[game][market][bet]
                # Calc average and fair odds
                stop()
                dict_element[keys_list[0]][0], dict_element[keys_list[1]][0],dict_element[keys_list[0]][1], dict_element[keys_list[1]][1], a1, a2 = calc_stuff(dict_element[keys_list[0]],dict_element[keys_list[1]])            
                       

    # Insert spread lines
    #dict[index]['spread']['away'][groups[0].text()[:4]] = groups[0].text()[4:] #spread away team
    #dict[index]['spread']['home'][groups[3].text()[:4]] = groups[3].text()[4:] #spread home team
        
        # Insert total lines
      #  moneyline_dict_dk[index]['total'][groups[1].text()[2:5]] = {'over':'', 'under':{}}
      #  moneyline_dict_dk[index]['total'][groups[1].text()[2:5]]['over']  = groups[1].text()[5:] #totals over
      #  moneyline_dict_dk[index]['total'][groups[1].text()[2:5]]['under'] = groups[4].text()[5:] #totals under
        
    # return parsed odds
    #return odds_dict

# Parse player prop lines
def parse_odds_player_prop(odds,market,dict):
    
    # Get list of player names
    player_names = get_player_names(odds)

    # loop through each player and extract odds from every book
    for player in player_names:
        
        # Each player's odds stored as a dict 
        player_dict = {}
        
        # Loop through books and extract player odds
        for book1 in odds['bookmakers']:
            
            # if book not in wanted list then skip
            if book1['key'] not in sportsbook_order: continue
            
            # Loop through all odds
            for a2 in book1['markets'][0]['outcomes']:
                
                # if player, then extract odds
                if a2['description'] == player:

                    # Check if a dict for this bet has already been initiated. If not, initiate it
                    if a2['point'] not in player_dict:
                        player_dict[a2['point']] = {'over':[''] * len(sportsbook_order),'under':[''] * len(sportsbook_order)}
     
                    # If Nan, ignore
                    if np.isnan(a2['price']):
                        value = ''
                        print('snanisnanisnanisnanisnan')
                        stop()
                    else:
                        value = a2['price']
          
                    # store odds at right place to align with sportsbook_order
                    if a2['name'] == 'Over':
                        player_dict[a2['point']]['over'][sportsbook_order.index(book1['key'])] = value

                    if a2['name'] == 'Under':
                        player_dict[a2['point']]['under'][sportsbook_order.index(book1['key'])] = value
                        
           
        # Store odds for the player in master dictionary
        if len(player_dict) > 0:
            
            # Check if this player already exists in master odds dictionary. If not, add it
            if player not in dict:
                dict[player] = {}
            
            # Add to the dict
            dict[player][market] = player_dict
            
# Get list of Players - must be json odds of a player prop (obviously)
def get_player_names(odds):
    player_names = []
    # loop through books and extract all player names
    for a1 in odds['bookmakers']:
        for a2 in a1['markets'][0]['outcomes']:
            if a2['description'] not in player_names:
                player_names.append(a2['description'])
    return player_names

# wrapper for looping through eventIds and extracting player prop odds, matching dk sgp odds, and calculating avg & fair odds
def player_prop_odds_wrapper(sport,markets,tomorrow_okay=False):
    
    # Get eventIds
    eventIds = get_eventIds(sport,tomorrow_okay=False)

    # loop through each game (event) and extract odds
    for i, event in enumerate(eventIds):
        
        # Get player prop odds for all markets at a single game then add add to master dictionary
        get_odds(sport,markets,props_dict,eventId=event,prop=True)

        # Calculate the average and fair odds for every bet and fill them into master dictionary
        calc_stuff_player_prop(props_dict)

        # Save 
        #save_pickle(dict,'hits_dic_test.pickle')
    
            
    # Match dk sgp odds
    match_dk_player_prop(props_dict)
    
# Load in DK sgp odds and put into full moneyline master array
def match_dk(sport,dict):
    
    # Open file containing DK scraped odds - first topen text file that gives correct filename of most recent saved dk sgp dictionary
    file = open('test_moneyline_restart.txt','r')
    fn = file.read()
    file.close()
    with open(fn, 'rb') as f: 
        moneyline_dict_dk = pickle.load(f) 
    master_keys = list(dict.keys())
    print('Draftkings SGP dictionary opened: ' + fn)

    
    # Loop through each game in dk sgp array
    for i, game in enumerate(list(moneyline_dict_dk)):
            
        # matching dk sgp index name to master dicts index name. Can be different (e.g., "Los-Angeles" vs. "LA")
        # Extract individual words from sgp team name game index and see how many match keys in master dict
        individual_words_sgp = list(map(str.lower,game.replace("-"," ").split()))
        
        # loop through each word in dk sgp key and count where matches a master dict key
        matched_words = [0]*len(master_keys) # Store number of matching words for each master dict key 
        for word1 in individual_words_sgp:
            for j, key1 in enumerate(master_keys):
                individual_words_master = list(map(str.lower,key1.replace("-"," ").split()))
                matched_words[j] += individual_words_master.count(word1)

        # Matching key must have at least two matching words (team names)
        try:
            if matched_words[np.argmax(matched_words)] < 2:
                print('\n \n Not enough matching words to match dk sgp and master dict')
                stop()
        except:stop()
        index = master_keys[np.argmax(matched_words)]
        print(game, index)

        # Add dk sgp odds ot master array - negative sgp odds not liking "-" symbol and cant convert. 
        # I will fix that in the loop
        for bet in moneyline_dict_dk[game]:
            
            # Separate moneyline from spread/totals
            if bet == 'h2h':
                
                # Fix negative signs if needed - replace the negative numbers with apropriate unicode character
                for sideside in moneyline_dict_dk[game][bet]:
                    if moneyline_dict_dk[game][bet][sideside][0] != '+': 
                        moneyline_dict_dk[game][bet][sideside] = '-' + moneyline_dict_dk[game][bet][sideside][1:]
          
                dict[index][bet]['away'][sportsbook_order.index('dk sgp')] = american_to_dec(float(moneyline_dict_dk[game][bet]['away']))
                dict[index][bet]['home'][sportsbook_order.index('dk sgp')] = american_to_dec(float(moneyline_dict_dk[game][bet]['home']))
                
                try:
                    dict[index][bet]['draw'][sportsbook_order.index('dk sgp')] = american_to_dec(float(moneyline_dict_dk[game][bet]['draw']))
                except:
                   print('No Draw Line')

                print(index,dict[index][bet])
            else:
                try:
                    # spreads/totals/etc.
                    for point in moneyline_dict_dk[game][bet]:
                        # Check if sgp bet is in the master dict. If not, then can skip
                        if point not in dict[index][bet]: continue
                        # Fix negative signs if needed - replace the negative numbers with apropriate unicode character
                        if moneyline_dict_dk[game][bet][point]['over'][0] != '+': 
                            moneyline_dict_dk[game][bet][point]['over'] = '-' + moneyline_dict_dk[game][bet][point]['over'][1:]
                        if moneyline_dict_dk[game][bet][point]['under'][0] != '+': 
                            moneyline_dict_dk[game][bet][point]['under'] = '-' + moneyline_dict_dk[game][bet][point]['under'][1:]
                                
                        # Add to master dict
                        dict[index][bet][point]['over'][sportsbook_order.index('dk sgp')] = american_to_dec(float(moneyline_dict_dk[game][bet][point]['over']))
                        dict[index][bet][point]['under'][sportsbook_order.index('dk sgp')] = american_to_dec(float(moneyline_dict_dk[game][bet][point]['under']))
                except:
                    print("no matching for " + bet)

# Load in DK sgp odds and put into full player prop odds array
def match_dk_player_prop(dict):

    # Open files containing DK scraped odds - firs topen text files that give filename of what need to load
    file = open('test_prop_restart.txt','r')
    fn_prop = file.read()
    file.close()
    with open(fn_prop, 'rb') as f: 
        props_dict_dk = pickle.load(f) 
    print('Draftkings SGP dictionary opened: ' + fn_prop)

    # Loop through dk sgp players
    for player in props_dict_dk:
        player_strip = player.strip()
        
        # Check if dk sgp in master dict - think this is redundant right now and can be deleted
        if player_strip not in dict:
            print('\n \n ' + player + '  sgp player not found in master dict \n \n')
            continue
        
        # Loop through all markets for that player - if dk sgp has wrong index name, change it
        for bet in props_dict_dk[player]: 
            if bet == 'player_home_runs': 
                new_bet = 'batter_home_runs'
            else:
                new_bet = bet

            # Check if market in master dict - if not skip
            if new_bet not in dict[player.strip()]:
                continue
            
            # Loop through each point (+1 then 2+ then 3+ rbi...)
            for point in props_dict_dk[player][bet]:
                
                # Check if market in master dict - if not skip
                if point not in dict[player.strip()][new_bet]:
                    continue
            
                # Add sgp odds to master odds array - negative sgp odds not liking "-" symbol and cant convert. Hence the try - if it works it is + odd else, negative (hopefully)
                try:
                    dict[player.strip()][new_bet][point]['over'][sportsbook_order.index('dk sgp')] = american_to_dec(float(props_dict_dk[player][bet][point]['over']))                                    ### ONLY GETS 1+ ODDS RIGHT NOW FROM SGP. No 2+,3+ or under odds
                except:
                    dict[player.strip()][new_bet][point]['over'][sportsbook_order.index('dk sgp')] = american_to_dec(-1.0 * float(props_dict_dk[player][bet][point]['over'][1:]))       

# Write all odds to google sheet
def sheets_update(data,worksheet_name):
    # initialize connection
    gc = pygsheets.authorize(client_secret='credentials.json')
    sh = gc.open('Test') # open spreadsheet

    # Pick worksheet 
    wk1 = sh.worksheet_by_title(worksheet_name)

    # Header columns
    wk1.update_row(1,[datetime.now().strftime("%Y-%m-%d %H:%M"),*sportsbook_order])
    
    keys_list = list(data.keys())
    i = 0
    row_i = 3
    for game1 in enumerate(data.keys()):
        print(i)
        if i > len(keys_list) - 2:
            break
        
        wk1.update_row(row_i,[keys_list[i],  *tb.dec_to_american(data[keys_list[i]]  ,array=True)])
        wk1.update_row(row_i+1,[keys_list[i+1],*tb.dec_to_american(data[keys_list[i+1]],array=True)])

        i = i+2
        
        row_i = row_i + 3 # controls space between games

# Write all player prop odds to google sheet - player props
def sheets_update_player_prop(data,worksheet_name):
    # initialize connection
    gc = pygsheets.authorize(client_secret='credentials.json')
    sh = gc.open('Test') # open spreadsheet

    # Pick worksheet 
    wk1 = sh.worksheet_by_title(worksheet_name)
    
    # Clear worksheet
    wk1.clear()

    # Header columns
    wk1.update_row(1,[datetime.now().strftime("%Y-%m-%d %H:%M"),'',*sportsbook_order])

    # Initialize indices
    i = 0
    row_i = 3
    
    # list of keys
    keys_list = data.keys()
    
    # Loop through players
    for player in data:
        
        # Loop through bets
        for bet in data[player]:
            
            #if i > len(keys_list) - 2:
            #    break
            
            wk1.update_row(row_i,  [player, 'o' + str(bet),  *tb.dec_to_american(data[player][bet]['Over']  ,array=True)])
            wk1.update_row(row_i+1,['',      'u' + str(bet) ,     *tb.dec_to_american(data[player][bet]['Under'],array=True)])

            i = i + 2
            row_i = row_i + 3 # controls space between games

# Write +ev bets to sheet
def sheets_update_plus_ev(data):
    # initialize connection
    gc = pygsheets.authorize(client_secret='credentials.json')
    sh = gc.open('Test') # open spreadsheet

    # Pick worksheet 
    wk1 = sh.worksheet_by_title('+ev')

    # Header columns
    wk1.update_row(1,[datetime.now().strftime("%Y-%m-%d %H:%M"),*sportsbook_order])
    
    keys_list = list(data.keys())
    i = 0
    row_i = 3
    for game1 in enumerate(data.keys()):
        print(i)
        #if i > len(keys_list) - 2:
         #   break
        
        stop()
        wk1.update_row(row_i,[keys_list[i],  *tb.dec_to_american(data[keys_list[i]]  ,array=True)])
        #wk1.update_row(row_i+1,[keys_list[i+1],*tb.dec_to_american(data[keys_list[i+1]],array=True)])

        i = i+2
        
        row_i = row_i + 3 # controls space between games

# Find +ev bets - works for moneyline/total/spreads dictionary
def find_plusEV(sport,odds_dict):
    
    # loop through every bet and determine if +ev wrt average oddsd
    
    for game in odds_dict:
        for market in odds_dict[game]:
            for bet in odds_dict[game][market]:
                
                # If empty bet odds (or just one book odds, then skip) must have 4 odds total
                arr = np.array(odds_dict[game][market][bet])
                if len(arr[arr!='']) < 4:
                    continue
                
                # Split moneyline and spreads/totals/etc.
                if market =='h2h':
                    fair_odd = odds_dict[game][market][bet][sportsbook_order.index('Fair')]
                    
                    if not(fair_odd):
                        print('\n \n Skippingplus - no fair odds!!! \n \n' + game + market)
                        continue
                    
                    # Loop through individual bets - if greater than fair then +ev. Save only if dk sgp
                    for i, o1 in enumerate(odds_dict[game][market][bet]):
                        
                        # skip string entries and entries that are the average or fair odds
                        if (i == sportsbook_order.index('Average')) or (i == sportsbook_order.index('Fair')) or (type(o1) == str):
                            continue
                        else:
                            # If +ev and dk sgp then save
                            try:
                                if (o1 > fair_odd) and ((i == sportsbook_order.index('dk sgp'))):
                                    plus_ev[game] = {'market':market,'lines':odds_dict[game][market][bet], 'bet':' ', 'side':' '} 
                            except:
                                pass
                            
                else: # spread/totals/etc.
                    for over_under in odds_dict[game][market][bet]:
                        fair_odd = odds_dict[game][market][bet][over_under][sportsbook_order.index('Fair')]

                        # Loop through individual bets - if greater than fair then +ev. Save only if dk sgp
                        for i, o1 in enumerate(odds_dict[game][market][bet][over_under]):
                            
                            # skip string entries and entries that are the average or fair odds
                            if (i == sportsbook_order.index('Average')) or (i == sportsbook_order.index('Fair')) or (type(o1) == str):
                                continue
                            else:
                                # If +ev and dk sgp then save
                                if (o1 > fair_odd) and ((i == sportsbook_order.index('dk sgp'))):
                                    plus_ev[game] = {'market':market,'lines':odds_dict[game][market][bet][over_under],'bet':bet,'side':over_under} 
                                    
    # print to csv file
    if not(plus_ev):
        print('\n No plus ev bets found')
    else:
        print('\n plus ev printed to spreadsheet')
    
    header =         [' ',            'Market',                    'Bet',                                                        'Fair',                                                     'DK sgp' ]
    new_array = [header]
    for game in plus_ev:
        try:
            new_array.append([game,    plus_ev[game]['market'],    plus_ev[game]['side'][0] + ' ' + str(plus_ev[game]['bet']),    plus_ev[game]['lines'][sportsbook_order.index('Fair')],    plus_ev[game]['lines'][sportsbook_order.index('dk sgp')]   ])
        except:
            stop()
        
        df = pd.DataFrame(new_array)
        print(df)
        df.to_csv('plus_ev_bets_' + sport + '.csv')
      
# Find +ev bets - Player props
def find_plusEV_player_prop(odds_dict):
    counter = 0
    for player in odds_dict:
        for bet in odds_dict[player]:
            for point in odds_dict[player][bet]:
                
                # Get fair odds for over/under
                try:
                    fair_odd_over = odds_dict[player][bet][point]['over'][sportsbook_order.index('Fair')]    
                    fair_odd_under = odds_dict[player][bet][point]['under'][sportsbook_order.index('Fair')]
                except:
                    continue
                
                # skip if no fair odd for this bet
                if not(fair_odd_over):
                    continue

                # Loop trough individual odds and check if +ev
                for j in range(len(odds_dict[player][bet][point]['over'])):
                    #print(type(odds_dict[player][bet]['Over'][j]))
                    
                    # skip fair and avg odds and any blank entries
                    if (j == sportsbook_order.index('Average')) or (j == sportsbook_order.index('Fair')):
                        continue
                    
                    # Over
                    if type(odds_dict[player][bet][point]['over'][j]) != str:
                        #print(type(odds_dict[player][bet]['Over'][j]),type(fair_odd_over))
                        
                        # Calculate ev of bet
                        try:
                            bet1ev = np.round((fair_odd_over)**(-1) * 100 * (odds_dict[player][bet][point]['over'][j] - 1)  -  (1 - (fair_odd_over)**(-1))*100,2)
                        except: 
                            pass
                        
                            
                        # If +ev save if dk sgp
                        if bet1ev > 0: print(np.round(bet1ev,2),player,odds_dict[player][bet][point])
                        if odds_dict[player][bet][point]['over'][j] > fair_odd_over:
                            #if j >=0: # keep all plus ev from all sportsbooks
                            if j == sportsbook_order.index('dk sgp'):  # only keep if the +ev bet is DK sgp
                                odds_dict[player][bet][point]['over'].append(bet1ev) # append ev to end of odds array
                              
                                # Check if player is in plus_ev, if so add subscript 2 to name, if not create entry
                                if player in plus_ev:
                                    player_string = player + '_' + str(counter)
                                    counter = counter + 1
                                else:
                                    player_string = player
                                plus_ev[player_string] = {}
                                
                                # add to master dict
                                plus_ev[player_string][point] =  {bet: odds_dict[player][bet][point]['over']}

                    # Under
                    if type(odds_dict[player][bet][point]['under'][j]) != str:
                        if odds_dict[player][bet][point]['under'][j] > fair_odd_under:
                            if j == sportsbook_order.index('dk sgp'):  # only keep if the +ev bet is DK sgp
                                odds_dict[player][bet][point]['under'].append(bet1ev) # append ev to end of odds array
                                
                                # Check if player is in plus_ev, if so add subscript 2 to name, if not create entry
                                if player in plus_ev:
                                    player_string = player + '_' + str(counter)
                                    counter = counter + 1
                                else:
                                    player_string = player
                                plus_ev[player_string] = {}
                                plus_ev[player_string][point] = {bet: odds_dict[player][bet][point]['under']}
                       
    # print plusev bets niceley
    evhold = []
    namehold = []
    pointhold = []
    for player in plus_ev:
        for bet in plus_ev[player]:
            for point in plus_ev[player][bet]:
                try:
                    evhold.append(plus_ev[player][bet][point][-1])
                    namehold.append(player)
                    pointhold.append(point)
                except:
                    continue

    print('\n \n \n')
    
    namesort = np.flip(np.array(namehold)[np.argsort(evhold)])# soted names by bets EV
    evsort = np.flip(np.array(evhold)[np.argsort(evhold)])

    # Print plus ev bets niceley to terminal
    
    for i, a in enumerate(namesort):
       print(evsort[i], namesort[i])
    print('\n')
        

##############################################################
 ### SET SPORTSBOOK ORDER
##############################################################
sportsbook_order = ['Average','Fair','dk sgp','fanduel','draftkings','williamhill_us','williamhill','tipico_us','betmgm','barstool','superbook','pointsbetus','bovada','bet365','betrivers','mrgreen','betus','betrivers','pinnacle']
#sportsbook_order = ['Average','Fair','dk sgp','betmgm','bovada','mrgreen','betus',,'pinnacle','Bovada']
#sportsbook_order = ['Average','Fair','dk sgp','fanduel','draftkings','williamhill_us']

# Prop keys  - these are the dict keys used for various player props
##############################################################
 ### TOGGLE SPORTS AND PLAYER PROPS ON/OFF
##############################################################
plus_ev = {}
props_dict = {}

###############################################################################################
 ### SOCCER  - oddsapi seems to lack a lot of these line stuck w/ moneline and totals right now
###############################################################################################
if False:
    soccer_dict = {}
    sport_pick = ['soccer_usa_mls']  #,'soccer_mexico_ligamx'] #choose leagues to scrape
    #ssport_pick = ['soccer_mexico_ligamx']
    sport_pick = ['soccer_fifa_world_cup_womens']
    for sport in sport_pick:
        
        # Get moneyline/total/spreads/etc. and put in master dictionary
        markets = ['h2h']
        get_odds(sport,markets,soccer_dict,eventId=None,prop=False)
            
        # Match dk sgp odds and ut into master dictionary
        match_dk(sport,soccer_dict)
        
        # Find plus ev bets
        find_plusEV(sport,soccer_dict)
        
        # Explore how bad sgp odds are compared to other books
        book_holds = []
        book_holds_sgp = []
        book_names = []
        theTAG = 'h2h'
        for game in soccer_dict:
            for i, bet1 in enumerate(soccer_dict[game][theTAG]['away']):
                #skip avg/fair odds
                if i < 2: continue

                # Over andunde rodds for one bet rom one sportsbook
                #odd_over = soccer_dict[game]['totals'][point]['over'][i]
                #odd_under = soccer_dict[game]['totals'][point]['under'][i]
                odd_over = soccer_dict[game][theTAG]['away'][i]
                odd_under = soccer_dict[game][theTAG]['home'][i]
                odd_draw = soccer_dict[game][theTAG]['draw'][i]
                #a1,a2 = fair_odds(odd_over,odd_under)
                
                # If no odds skip
                if not(odd_over): continue
                if not(odd_under): continue
            
                # Calculate hold
                hold1 = 1 * (1/odd_over + 1/odd_under + 1/odd_draw) - 1
              
                # store holds for sgp and other books
                if i == sportsbook_order.index('dk sgp'): 
                    book_holds_sgp.append(100*hold1) #in %
                    print(game)
                else:
                    book_holds.append(100*hold1)
                    book_names.append(sportsbook_order[i])
                
        #plt.scatter(book_names,book_holds)
        #plt.scatter(['DK SGP'] * len(book_holds_sgp), book_holds_sgp)
        from matplotlib import cycler
        colors = cycler('color',
                        ['#EE6666', '#3388BB', '#9988DD',
                        '#EECC55', '#88BB44', '#FFBBBB'])
        plt.rc('axes', facecolor='#E6E6E6', edgecolor='none',
            axisbelow=True, grid=True, prop_cycle=colors)
        plt.rc('grid', color='w', linestyle='solid')
        plt.rc('xtick', direction='out', color='gray')
        plt.rc('ytick', direction='out', color='gray')
        plt.rc('patch', edgecolor='#E6E6E6')
        plt.rc('lines', linewidth=2)
        plt.rc('font', size=12,weight='bold')  
        #mpl.rcParams['xtick.minor.width'] = 0.75
        #plt.rc('font', size=5)#,weight='bold')   
        
        bins = np.arange(0,16,1)
        plt.hist(book_holds,weights=np.ones_like(book_holds)/len(book_holds),bins=bins,edgecolor='#E6E6E6')
        plt.hist(book_holds_sgp,weights=np.ones_like(book_holds_sgp)/len(book_holds_sgp),bins=bins,color='#9AC434',edgecolor='#E6E6E6')
        plt.xlim(0,15)
        plt.ylim(0,0.6)
        #plt.grid(color='w', linestyle='solid')
        plt.xlabel('Book Hold (%)')
        plt.ylabel('Density (fraction of bets w/ given hold %)')
        plt.tight_layout()
        #plt.scatter(['DK SGP'] * len(book_holds_sgp), book_holds_sgp)
        plt.savefig('soccer_bad_lines.pdf',dpi=300)
        plt.close()

##############################################################
 ### BASEBALL - MLB
##############################################################
if True:
    baseball_dict = {}
    sport = 'baseball_mlb'

    plus_ev ={}
    # Moneyline, Totals, Spreads
    if False:
        get_odds(sport,['h2h','totals'],baseball_dict,eventId=None,prop=False)
        match_dk(sport,baseball_dict)
        find_plusEV(sport,baseball_dict)
        
        
        # Save final dicts to store historical odds
        fn = 'complete_odds/moneyline' + sport + '_' + str(Time.now().jd).replace(".","_")
        with open(fn, 'wb') as f:       pickle.dump(ml_dict,f)

    # player props
    if True:
        plus_ev ={}
        # Combone oddsAPI and dk sgp odds to master dict, calc average & fair odds and add to master dict
        player_prop_odds_wrapper(sport,['batter_hits','pitcher_hits_allowed','batter_rbis','batter_total_bases','pitcher_strikeouts'])#',pitcher_strikeouts])

    # Find plus ev bets
    find_plusEV_player_prop(props_dict)

    # print plus evbets
    for a in plus_ev:
        print(a, plus_ev[a].keys(), list(plus_ev[a].values())[0].keys(),tb.dec_to_american(list(list(plus_ev[a].values())[0].values())[0],array=True))

    # Save final dicts to have database of historical odds
    fn_prop = 'saved_data/complete_odds/props_' + sport + '_' + str(Time.now().jd).replace(".","_")
    with open(fn_prop, 'wb') as f:  pickle.dump(props_dict,f)


