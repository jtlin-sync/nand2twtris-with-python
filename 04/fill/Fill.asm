// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Fill.asm

// Runs an infinite loop that listens to the keyboard input.
// When a key is pressed (any key), the program blackens the screen,
// i.e. writes "black" in every pixel;
// the screen should remain fully black as long as the key is pressed. 
// When no key is pressed, the program clears the screen, i.e. writes
// "white" in every pixel;
// the screen should remain fully clear as long as no key is pressed.

// Put your code here.
    @8192
    D=A
    @full
    M=D  // full = 256 * 512 / 16 = 8192
    
(SCANLOOP)
    @i
    M=0 // i = 0

    @KBD
    D=M
    @NOINPUT
    D;JEQ

(BLACKLOOP)
    @i
    D=M
    @full  
    D=D-M
    @SCANLOOP
    D; JEQ // i - full >= 0 => jump to scanloop
    @i
    D=M
    @SCREEN
    A=D+A
    M=-1 // blacken
    @i
    M=M+1
    @BLACKLOOP
    0; JMP

(NOINPUT)
(WHITELOOP)
    @i
    D=M
    @full
    D=D-M
    @SCANLOOP
    D; JEQ // i - full >= 0 => jump to scanloop
    @i
    D=M
    @SCREEN
    A=D+A
    M=0 // clear
    @i
    M=M+1
    @WHITELOOP
    0; JMP
