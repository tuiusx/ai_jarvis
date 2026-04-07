param(
    [switch]$SkipTests
)

$argsList = @("superpowers.py")
if ($SkipTests) {
    $argsList += "--skip-tests"
}

python @argsList
