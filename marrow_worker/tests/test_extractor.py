from src.parser import extract_skeleton


def test_extract_csharp():
    source = b"""
using System;

namespace MyProject
{
    public abstract class BaseManager 
    {
        public bool IsActive { get; set; } = true;
        
        public BaseManager(string name)
        {
            Console.WriteLine("Init: " + name);
            IsActive = false;
        }

        protected virtual void DoWork(int count)
        {
            for (int i=0; i<count; i++) 
            {
                Console.WriteLine(i);
            }
        }
    }
}
"""
    skeleton = extract_skeleton(source, ".cs")

    # We expect the class, namespace, and method declarations to be preserved intact, but block bodies stubs.
    assert (
        "public virtual void DoWork(int count)" in skeleton
        or "protected virtual void DoWork(int count)" in skeleton
    )
    assert "{ /* ... implementation */ }" in skeleton
    assert "Console.WriteLine" not in skeleton


def test_extract_python():
    source = b"""
import os

class AuthManager:
    \"\"\"Handles user authentication\"\"\"
    
    def __init__(self, token: str):
        self.token = token
        self.is_valid = self._validate()
        
    def login(self, username: str) -> bool:
        # A comment here
        print(f"Logging in {username}")
        return True
"""
    skeleton = extract_skeleton(source, ".py")

    assert "def login(self, username: str) -> bool:" in skeleton
    assert "def __init__(self, token: str):" in skeleton
    assert "self.token = token" not in skeleton
    assert 'print(f"Logging in {username}")' not in skeleton
    assert "class AuthManager:" in skeleton
    assert '"""Handles user authentication"""' in skeleton


def test_extract_typescript():
    source = b"""
export interface User {
    id: number;
    name: string;
}

export class UserService implements User {
    id: number;
    name: string;

    constructor(id: number) {
        this.id = id;
        this.name = "Test";
    }

    async fetchDetails(force: boolean): Promise<void> {
        if (force) {
            await fetch('/api/user');
        }
    }
}
"""
    skeleton = extract_skeleton(source, ".ts")

    assert "export class UserService implements User" in skeleton
    assert "constructor(id: number) { /* ... implementation */ }" in skeleton
    assert (
        "async fetchDetails(force: boolean): Promise<void> { /* ... implementation */ }" in skeleton
    )
    assert "await fetch" not in skeleton
