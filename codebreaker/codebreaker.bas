1 REM CODEBREAKER FOR THE ALTAIDS COMPUTER, 2024 BY ROB GLAZEBROOK
2 REM BASED ON THE VERSION FROM TINYBASIC.CYNINGSTAN.ORG.UK
3 REM S = SECRET NUMBER, T = TEMP SECRET, U = DIGIT FROM SECRET
4 REM P = PLAYER'S GUESS, C = TEMP GUESS, D = DIGIT FROM GUESS
4 REM B = BLACK PEGS, W = WHITE PEGS
5 REM G = NUMBER OF GUESSES
6 REM M = MULTIPLIER FOR CHECKING SPECIFIC DIGIT LOCATIONS
7 REM N = MULTIPLIER FOR LOOPING ACROSS SECRET NUMBER LOCATIONS
8 REM L = GUESS NUMBER LENGTH (1 OR 2 DIGITS)
9 REM Y = PLAY AGAIN?

10 REM START THE GAME
11 CLS : PRINT : PRINT ". : C O D E B R E A K E R : ." : PRINT
12 RANDOMIZE : S = RND(6)*1000 + RND(6)*100 + RND(6) * 10 + RND(6)
13 PRINT "I'VE CHOSEN A SECRET NUMBER. IT HAS 4 DIGITS RANGING"
14 PRINT "FROM 1-6. YOU GET 10 TRIES TO GUESS MY NUMBER."
15 PRINT "I'LL GIVE YOU A BLACK PEG FOR EACH CORRECT DIGIT IN THE"
16 PRINT "RIGHT POSITION, AND A WHITE PEG FOR EACH CORRECT"
17 PRINT "DIGIT IN THE WRONG POSITION." : PRINT 
18 G = 0

20 REM GET THE PLAYER'S GUESS
21 PRINT "GUESS #", : L = (G + 1)/10 + 1 :  PRINT#L, G + 1
22 INPUT "WHAT IS YOUR GUESS" P
23 IF (P<1111)+(P>9999) PRINT "WRONG NUMBER OF DIGITS." : PRINT : GOTO 22
24 M = 1
25 D = P/M : D = D - D/10 * 10
26 IF (D>6) + (D=0) PRINT "ONLY USE DIGITS 1-6." : PRINT : GOTO 22
27 M = M * 10 : IF M <= 1000 GOTO 25
28 G = G + 1

30 REM EVALUATE THE GUESS
31 B=0 : W=0 : T=S : C=P : M=1
32 GOSUB 40
33 M = M * 10 : IF M <= 1000 GOTO 32
34 M = 1
35 GOSUB 50
36 M = M * 10 : IF M <= 1000 GOTO 35
37 PRINT "PEGS: ",:PRINT#1,B,:PRINT " BLACK, ",:PRINT#1,W,:PRINT " WHITE."
38 PRINT : IF (G<10) * (B<>4) GOTO 21
39 GOTO 60

40 REM CHECK FOR AN EXACT MATCH
41 D = C/M : D = D - D/10 * 10
42 U = T/M : U = U - U/10 * 10
43 IF D<>U RETURN
44 B = B + 1
45 C = C - M * D : T = T - M * U
46 RETURN

50 REM CHECK FOR A MATCH ACROSS ALL 4 POSITIONS
51 D = C/M : D = D - D/10 * 10  : N = 1
52 U = T/N : U = U - U/10 * 10
53 IF (D>0) * (U>0) * (D=U) GOTO 56
54 N = N * 10 : IF N <= 1000 GOTO 52
55 RETURN
56 W = W + 1
57 C = C - M * D : T = T - N * U
58 RETURN

60 REM GAME OVER
61 IF B=4 GOTO 65
62 PRINT "YOU LOST AFTER 10 GUESSES."
63 PRINT "THE SECRET NUMBER WAS ", : PRINT#4, S
64 GOTO 67
65 PRINT "YOU WON IN ", : PRINT#L,G, : PRINT " GUESSES!"
66 PRINT "THE NUMBER WAS INDEED ", : PRINT#4, S
67 PRINT : INPUT "ENTER 1 TO PLAY AGAIN, OR ANYTHING ELSE TO QUIT" Y
68 IF Y=1 GOTO 10
69 PRINT "THANKS FOR PLAYING!" : END
