VALID_PROGRAMS = [
    # 1. Minimal valid program
    """
    main: {
    }
    """,
    ################################
    # Statements
    ################################
    # 6. While loop
    """
    main: {
        var x = 0;
        while (x < 10) {
            x = x + 1;
        }
    }
    """,
    # 7. Repeat-until loop
    """
    main: {
        var x = 0;
        repeat {
            x = x + 1;
        } until (x == 5);
    }
    """,
    # 8. For loop
    """
    main: {
        for (i : int; i = 0; i < 10; i = i + 1) {
            print("loop");
        }
    }
    """,
    # 15. Scan + Print
    """
    main: {
        var x : int;
        scan(x);
        print("read");
    }
    """,
    # 12. Void function
    """
    void greet(name : str) {
        print("hello");
        return;
    }

    main: {
        greet("world");
    }
    """,
    # 19. nesting
    """
    main: {
        if (true) {
            while (true) {
                repeat {
                    print("loop");
                } until (false);
            }
        } else {
            print("end");
        }
    }
    """,
    ################################
    # Declarations
    ################################
    # 2. const and var declarations
    """
    main: {
        let x = 10;
        var y: int;
        var z = 3;
    }
    """,
    # 18. Multiple declarations
    """
    record A { x : int; };
    record B { y : A; };

    int f(a : A, b : B) {
        return 1;
    }

    main: {
        var a : A;
        var b : B;
        var x = f(a, b);
    }
    """,
    # 20. Expression-only statements
    """
    main: {
        1 + 2 + 3;
        true && false;
        (3 * 4);
    }
    """,
    ################################
    # Expressions
    ################################
    # 9. Arrays
    """
    main: {
        var arr1: int arr [10];
        arr1[0] = 5;
        arr1[1] = arr1[0] + 3;

        var arr2: float arr[2, 2, 2];
        arr2[0, 0, 0] = 5;
    }
    """,
    # 10. Records
    """
    record Person {
        age : int;
        name : str;
    };

    main: {
        var p : Person;
        p.age = 20;
        print("done");
    }
    """,
    # 3. Arithmetic
    """
    main: {
        var x = 1 + 2 * 3;
        var y = (1 + 2) * 3;
        var z = 10 / 2 + 4 * 5;
    }
    """,
    # 4. Boolean expressions
    """
    main: {
        var a = true;
        var b = false;
        if (a && !b || a) {
            print("yes");

        } else {
            print("no");
        }
    }
    """,
    # 5. Relational expressions
    """
    main: {
        if (3 < 4) {
            print("lt");
        } else {
            print("nope");
        }

        if (5 >= 5) {
            print("ge");
        } else {
            print("bad");
        }
    }
    """,
    # 16. Complex mixed expressions
    """
    main: {
        var x = (3 + 4) * 2 > 10 && !false || true;
    }
    """,
    # 11. Function invocation
    """
    int add(a : int, b : int) {
        return a + b;
    }

    main: {
        var x = add(3, 4);
        print("ok");
    }
    """,
    # 13. Nested function calls
    """
    int add(a : int, b : int) {
        return a + b;
    }

    int mul(a : int, b : int) {
        return a * b;
    }

    main: {
        var x = mul(add(1, 2), add(3, 4));
    }
    """,
]
