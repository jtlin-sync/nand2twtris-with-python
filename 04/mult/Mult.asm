// This file is part of www.nand2tetris.org
// and the book "The Elements of Computing Systems"
// by Nisan and Schocken, MIT Press.
// File name: projects/04/Mult.asm

// Multiplies R0 and R1 and stores the result in R2.
// (R0, R1, R2 refer to RAM[0], RAM[1], and RAM[2], respectively.)
//
// This program only needs to handle arguments that satisfy
// R0 >= 0, R1 >= 0, and R0*R1 < 32768.

// Put your code here.
    @R0
    D=M
    @x
    M=D // x = R0

    @R1
    D=M
    @y
    M=D // y = R1

    @R2
    M=0 // sum(R2) = 0

    @i
    M=0 // i = 0

    @x
    D=M
    @y
    D=D-M // x - y
    @XSMALLER
    D; JLT // x - y < 0 => jump to xsmaller

(LOOPA)
    @i
    D=M
    @y
    D=D-M 
    @END
    D; JGE // i - y >= 0 => jump to END
    
    @x
    D=M
    @R2
    M=D+M // sum = x + sum
    
    @i
    M=M+1 // i ++

    @LOOPA
    0; JMP

(XSMALLER)
(LOOPB)
    @i
    D=M
    @x
    D=D-M 
    @END
    D; JGE // i - x >= 0 => jump to END
    
    @y
    D=M
    @R2
    M=D+M // sum = y + sum
    
    @i
    M=M+1 // i ++

    @LOOPB
    0; JMP

(END)
    @END
    0; JMP