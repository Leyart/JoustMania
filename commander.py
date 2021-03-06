import common
import psmove
import time
import psutil, os
import random
import numpy
from piaudio import Audio
from enum import Enum
from multiprocessing import Process, Value, Array


# How fast/slow the music can go
SLOW_MUSIC_SPEED = 1.5
#this was 0.5
FAST_MUSIC_SPEED = 0.5

# The min and max timeframe in seconds for
# the speed change to trigger, randomly selected
MIN_MUSIC_FAST_TIME = 4
MAX_MUSIC_FAST_TIME = 8
MIN_MUSIC_SLOW_TIME = 10
MAX_MUSIC_SLOW_TIME = 23

#Sensitivity of the contollers
#changes by the values in common
#TODO: make commander should be harder to kill
SLOW_MAX = 1.3
SLOW_WARNING = 0.28
FAST_MAX = 2.5
FAST_WARNING = 1.3



#How long the speed change takes
INTERVAL_CHANGE = 1.5

#How long the winning moves shall sparkle
END_GAME_PAUSE = 4


class Opts(Enum):
    alive = 0
    selection = 1
    holding = 2
    team = 3
    is_commander = 4

class Selections(Enum):
    nothing = 0
    a_button = 1
    trigger = 2
    triangle = 3

class Holding(Enum):
    not_holding = 0
    holding = 1

class Buttons(Enum):
    middle = 524288
    all_buttons = 240
    sync = 65536
    start = 2048
    select = 256
    circle = 32
    triangle = 16
    nothing = 0

class Bool(Enum):
    no = 0
    yes = 1


#red blue
Commander_colors = [(255,0,0),(0,0,255)]
Overdrive_colors = [(255,127,0),(0,255,255)]
Current_commander_colors = [(255,0,255),(0,255,0)]

class Team(Enum):
    red = 0
    blue = 1


def calculate_flash_time(r,g,b, score):
    flash_percent = max(min(float(score)+0.2,1.0),0.0)
    #val_percent = (val-(flash_speed/2))/(flash_speed/2)
    new_r = int(common.lerp(255, r, flash_percent))
    new_g = int(common.lerp(255, g, flash_percent))
    new_b = int(common.lerp(255, b, flash_percent))
    return (new_r, new_g, new_b)

def track_move(move_serial, move_num, team, team_num, dead_move, force_color, music_speed, commander_intro, move_opts, power, overdrive):
    #proc = psutil.Process(os.getpid())
    #proc.nice(3)


    start = False
    no_rumble = time.time() + 1
    move_last_value = None
    move = common.get_move(move_serial, move_num)
    team_colors = common.generate_colors(team_num)
    #keep on looping while move is not dead
    ready = False
    move.set_leds(0,0,0)
    move.update_leds()
    time.sleep(1)

    death_time = 8
    time_of_death = time.time()

    while commander_intro.value == 1:
        if move.poll():
            button = move.get_buttons()
            if button == Buttons.middle.value and move_opts[Opts.holding.value] == Holding.not_holding.value:

                move_opts[Opts.selection.value] = Selections.a_button.value
                move_opts[Opts.holding.value] = Holding.holding.value
            elif button == Buttons.triangle.value and move_opts[Opts.holding.value] == Holding.not_holding.value:

                move_opts[Opts.selection.value] = Selections.triangle.value
                move_opts[Opts.holding.value] = Holding.holding.value

            elif move_opts[Opts.is_commander.value] == Bool.no.value and move_opts[Opts.holding.value] == Holding.holding.value:
                move.set_leds(200,200,200)

            elif move_opts[Opts.is_commander.value] == Bool.yes.value and move_opts[Opts.holding.value] == Holding.holding.value:
                    move.set_leds(*Current_commander_colors[team])
            else:
                move.set_leds(*Commander_colors[team])
        move.update_leds()

    move_opts[Opts.holding.value] = Holding.not_holding.value
    move_opts[Opts.selection.value] = Selections.nothing.value

    while True:
        if sum(force_color) != 0:
            no_rumble_time = time.time() + 5
            time.sleep(0.01)
            move.set_leds(*force_color)
            move.update_leds()
            move.set_rumble(0)
            no_rumble = time.time() + 0.5
        #if we are not dead
        elif dead_move.value == 1:
            if move.poll():
                ax, ay, az = move.get_accelerometer_frame(psmove.Frame_SecondHalf)
                total = sum([ax, ay, az])
                if move_last_value is not None:
                    change = abs(move_last_value - total)

                    if move_opts[Opts.is_commander.value] == Bool.no.value:
                        if overdrive.value == 0:
                            warning = SLOW_WARNING
                            threshold = SLOW_MAX
                        else:
                            warning = FAST_WARNING
                            threshold = FAST_MAX
                    else:
                        #if affected by overdrive, this could make the power better
                        warning = SLOW_WARNING
                        threshold = SLOW_MAX
                        

                    if change > threshold:
                        if time.time() > no_rumble:
                            move.set_leds(0,0,0)
                            move.set_rumble(90)
                            dead_move.value = 0
                            time_of_death = time.time()

                    elif change > warning:
                        if time.time() > no_rumble:
                            move.set_leds(20,50,100)
                            move.set_rumble(110)

                    else:
                        if move_opts[Opts.is_commander.value] == Bool.no.value:
                            if overdrive.value == 0:
                                move.set_leds(*Commander_colors[team])
                            else:
                                move.set_leds(*Overdrive_colors[team])
                        else:
                            move.set_leds(*calculate_flash_time(Current_commander_colors[team][0],Current_commander_colors[team][1],Current_commander_colors[team][2], power.value))
                        move.set_rumble(0)


                    if move_opts[Opts.is_commander.value] == Bool.yes.value:
                        if (move.get_buttons() == 0 and move.get_trigger() < 10):
                            move_opts[Opts.holding.value] = Holding.not_holding.value
                            
                        button = move.get_buttons()
                        #print str(power.value)
                        if power.value >= 1.0:
                            #press trigger for overdrive
                            if (move_opts[Opts.holding.value] == Holding.not_holding.value and move.get_trigger() > 100):
                                move_opts[Opts.selection.value] = Selections.trigger.value
                                move_opts[Opts.holding.value] = Holding.holding.value

                        
                move_last_value = total
            move.update_leds()
        #if we are dead
        elif dead_move.value <= 0:
            if time.time() - time_of_death >= death_time:
                dead_move.value = 3
        elif dead_move.value == 3:
                move_last_value = None
                dead_move.value = 1
                no_rumble = time.time() + 2
                if death_time < 25:
                    death_time += 2
            

class Commander():
    def __init__(self, moves, speed):
        global SLOW_MAX
        global SLOW_WARNING
        global FAST_MAX
        global FAST_WARNING
        
        SLOW_MAX = common.SLOW_MAX[speed]
        SLOW_WARNING = common.SLOW_WARNING[speed]
        FAST_MAX = common.FAST_MAX[speed]
        FAST_WARNING = common.FAST_WARNING[speed]

        self.move_serials = moves
        self.tracked_moves = {}
        self.dead_moves = {}
        self.teams = {}
        self.music_speed = Value('d', 1)
        self.running = True
        self.force_move_colors = {}
        self.team_num = 2
        self.werewolf_timer = 35
        self.start_timer = time.time()
        self.audio_cue = 0

        self.move_opts = {}
        self.current_commander = ["",""]

        self.time_to_power = [20,20]
        self.activated_time = [time.time(), time.time()]

        self.activated_overdrive = [time.time(), time.time()]
        
        
        self.powers = [Value('d', 0.0), Value('d', 0.0)]

        self.red_overdrive = Value('i', 0)
        self.blue_overdrive = Value('i', 0)

        
        self.generate_random_teams(self.team_num)
        self.commander_intro = Value('i', 1)

        self.powers_active = [False, False]

        

        try:
            music = 'audio/Commander/music/' + random.choice(os.listdir('audio/Commander/music'))
        except:
            print('no music in audio/Commander/music')
        self.start_beep = Audio('audio/Joust/sounds/start.wav')
        self.start_game = Audio('audio/Joust/sounds/start3.wav')
        self.explosion = Audio('audio/Joust/sounds/Explosion34.wav')
        fast_resample = False
        end = False
        try:
            self.audio = Audio(music, end)
        except:
            print('no audio loaded')
        #self.change_time = self.get_change_time(speed_up = True)
        self.change_time = time.time() + 8
        self.speed_up = True
        self.currently_changing = False
        self.game_end = False
        self.winning_moves = []
        
        self.game_loop()


    def generate_random_teams(self, team_num):
        team_pick = list(range(team_num))
        for serial in self.move_serials:
            random_choice = random.choice(team_pick)
            self.teams[serial] = random_choice
            team_pick.remove(random_choice)
            if not team_pick:
                team_pick = list(range(team_num))

    def track_moves(self):
        for move_num, move_serial in enumerate(self.move_serials):
            time.sleep(0.02)
            dead_move = Value('i', 1)
            force_color = Array('i', [1] * 3)
            opts = Array('i', [0] * 5)
            power = self.powers[self.teams[move_serial]]

            if self.teams[move_serial] == Team.red.value:
                overdrive = self.red_overdrive
            else:
                overdrive = self.blue_overdrive
            proc = Process(target=track_move, args=(move_serial,
                                                    move_num,
                                                    self.teams[move_serial],
                                                    self.team_num,
                                                    dead_move,
                                                    force_color,
                                                    self.music_speed,
                                                    self.commander_intro,
                                                    opts,
                                                    power,
                                                    overdrive))
            proc.start()
            self.tracked_moves[move_serial] = proc
            self.dead_moves[move_serial] = dead_move
            self.force_move_colors[move_serial] = force_color
            self.move_opts[move_serial] = opts
            
    def change_all_move_colors(self, r, g, b):
        for color in self.force_move_colors.values():
            common.change_color(color, r, g, b)

    #need to do the count_down here
    def count_down(self):
        self.change_all_move_colors(80, 0, 0)
        self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(70, 100, 0)
        self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(0, 70, 0)
        self.start_beep.start_effect()
        time.sleep(0.75)
        self.change_all_move_colors(0, 0, 0)
        self.start_game.start_effect()
        
    def get_change_time(self, speed_up):
        if speed_up:
            added_time = random.uniform(MIN_MUSIC_FAST_TIME, MAX_MUSIC_FAST_TIME)
        else:
            added_time = random.uniform(MIN_MUSIC_SLOW_TIME, MAX_MUSIC_SLOW_TIME)
        return time.time() + added_time


    def get_winning_team_members(self, winning_team):
        self.end_game_sound(winning_team)
        for move_serial in self.teams.keys():
            if self.teams[move_serial] == winning_team:
                self.winning_moves.append(move_serial)

    def check_end_game(self):
        winning_team = -100
        team_win = False
        for commander in self.current_commander:
            if self.dead_moves[commander].value <= 0:
                winning_team = (self.teams[commander] + 1) % 2
                self.get_winning_team_members(winning_team)
                self.game_end = True
                

        for move_serial, dead in self.dead_moves.items():
            if dead.value == 0:
                dead_team = self.teams[move_serial]
                winning_team = (self.teams[move_serial] + 1) % 2
                if self.time_to_power[winning_team] > 15:
                    self.time_to_power[winning_team] -= 1
                if self.time_to_power[dead_team] < 25:
                    self.time_to_power[dead_team] += 1
                
                #This is to play the sound effect
                dead.value = -1
                self.explosion.start_effect()


    def stop_tracking_moves(self):
        for proc in self.tracked_moves.values():
            proc.terminate()
            proc.join()
            time.sleep(0.02)

    def end_game(self):
        try:
            self.audio.stop_audio()
        except:
            print('no audio loaded to stop')
        end_time = time.time() + END_GAME_PAUSE
        h_value = 0

        while (time.time() < end_time):
            time.sleep(0.01)
            win_color = common.hsv2rgb(h_value, 1, 1)
            for win_move in self.winning_moves:
                win_color_array = self.force_move_colors[win_move]
                common.change_color(win_color_array, *win_color)
            h_value = (h_value + 0.01)
            if h_value >= 1:
                h_value = 0
        self.running = False

    def end_game_sound(self, winning_team):
        #if self.game_mode == common.Games.JoustTeams:
        if winning_team == Team.red.value:
            team_win = Audio('audio/Commander/sounds/red winner.wav')
        if winning_team == Team.blue.value:
            team_win = Audio('audio/Commander/sounds/blue winner.wav')
        team_win.start_effect()

    def check_commander_select(self):
        for move_serial in self.move_opts.keys():
            if self.move_opts[move_serial][Opts.selection.value] == Selections.triangle.value and self.move_opts[move_serial][Opts.holding.value] == Holding.holding.value:
                Audio('audio/Commander/sounds/commanderselect.wav').start_effect()
                self.change_commander(move_serial)
                self.move_opts[move_serial][Opts.selection.value] = Selections.nothing.value
            elif self.move_opts[move_serial][Opts.selection.value] == Selections.a_button.value and self.move_opts[move_serial][Opts.holding.value] == Holding.holding.value:
                Audio('audio/Commander/sounds/buttonselect.wav').start_effect()
                self.move_opts[move_serial][Opts.selection.value] = Selections.nothing.value

    def change_commander(self, new_commander):
        #print 'changing commander to ' + str(new_commander)
        commander_team = self.teams[new_commander]
        if self.current_commander[commander_team] != '':
            self.move_opts[self.current_commander[commander_team]][Opts.is_commander.value] = Bool.no.value
        
        self.move_opts[new_commander][Opts.is_commander.value] = Bool.yes.value
        self.current_commander[commander_team] = new_commander

    def change_random_commander(self, team, exclude_commander=None):
        team_move_serials = [ move_serial for move_serial in self.move_opts.keys() if (self.teams[move_serial] == team and move_serial != exclude_commander and self.dead_moves[move_serial].value >= 1) ]
        print ('team move serials is ' + str(team_move_serials))
        if len(team_move_serials) > 0:
            new_commander = random.choice(team_move_serials)
            self.change_commander(new_commander)
            return True
        return False
            
    def update_team_powers(self):
        self.powers[Team.red.value].value = max(min((time.time() - self.activated_time[Team.red.value])/(self.time_to_power[Team.red.value] * 1.0),1.0), 0.0)
        self.powers[Team.blue.value].value = max(min((time.time() - self.activated_time[Team.blue.value])/(self.time_to_power[Team.blue.value] * 1.0), 1.0), 0.0)

        
        if self.powers_active[Team.red.value] == False:
            if self.powers[Team.red.value].value >= 1.0:
                self.powers_active[Team.red.value] = True
                Audio('audio/Commander/sounds/power ready.wav').start_effect()
                Audio('audio/Commander/sounds/red power ready.wav').start_effect()
                
                
        if self.powers_active[Team.blue.value] == False:
            if self.powers[Team.blue.value].value >= 1.0:
                self.powers_active[Team.blue.value] = True
                Audio('audio/Commander/sounds/power ready.wav').start_effect()
                Audio('audio/Commander/sounds/blue power ready.wav').start_effect()
                
            
    def overdrive(self, team):
        Audio('audio/Commander/sounds/overdrive.wav').start_effect()
        if team == Team.red.value:
            self.red_overdrive.value = 1
            self.activated_overdrive[Team.red.value] = time.time() + 10
            Audio('audio/Commander/sounds/red overdrive.wav').start_effect()
        else:
            self.blue_overdrive.value = 1
            self.activated_overdrive[Team.blue.value] = time.time() + 10
            Audio('audio/Commander/sounds/blue overdrive.wav').start_effect()

        
        
    def check_end_of_overdrive(self):
        if self.red_overdrive.value == 1:

            if time.time() >= self.activated_overdrive[Team.red.value]:
                #print 'its over'
                self.red_overdrive.value = 0
        if self.blue_overdrive.value == 1:
            
            if time.time() >= self.activated_overdrive[Team.blue.value]:
                #print 'itsa over'
                self.blue_overdrive.value = 0

    def reset_power(self, team):
        self.powers[team].value == 0.0
        self.activated_time[team] = time.time()
        self.powers_active[team] = False

    def check_commander_power(self):
        for commander in self.current_commander:
            #print self.move_opts[commander][Opts.selection] 
            if self.move_opts[commander][Opts.selection.value] == Selections.trigger.value:
                self.overdrive(self.teams[commander])
                self.reset_power(self.teams[commander])
                self.move_opts[commander][Opts.selection.value] = Selections.nothing.value


    def check_everyone_in(self):
        for move_serial in self.move_opts.keys():
            if self.move_opts[move_serial][Opts.holding.value] == Holding.not_holding.value:
                return False
        return True
        
            
    def commander_intro_audio(self):
        intro_sound = Audio('audio/Commander/sounds/commander intro.wav')
        intro_sound.start_effect()
        #need while loop here
        play_last_one = True
        commander_select_time = time.time() + 50
        battle_ready_time = time.time() + 40
        while time.time() < commander_select_time:
            self.check_commander_select()
            if self.check_everyone_in():
                break

            if time.time() > battle_ready_time and play_last_one:
                play_last_one = False
                Audio('audio/Commander/sounds/10 seconds begins.wav').start_effect()
        intro_sound.stop_effect()        

        if self.current_commander[Team.red.value] == '':
            self.change_random_commander(Team.red.value)
        if self.current_commander[Team.blue.value] == '':
            self.change_random_commander(Team.blue.value)


        Audio('audio/Commander/sounds/commanders chosen.wav').start_effect()
        time.sleep(4)
        self.reset_power(Team.red.value)
        self.reset_power(Team.blue.value)
        self.commander_intro.value = 0

    def game_loop(self):
        self.track_moves()
        self.commander_intro_audio()
        
        self.count_down()
        time.sleep(0.02)
        try:
            self.audio.start_audio_loop()
        except:
            print('no audio loaded to start')
        time.sleep(0.8)
        
        while self.running:
            self.update_team_powers()
            self.check_commander_power()
            self.check_end_of_overdrive()
            self.check_end_game()
            if self.game_end:
                self.end_game()

        self.stop_tracking_moves()
                    
                
                
        
        

            
        

            
