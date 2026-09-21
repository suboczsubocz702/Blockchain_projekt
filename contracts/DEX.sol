// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;


interface IERC20 {
	function transfer(address to, uint256 amount) external returns (bool);
	function transferFrom(address from, address to, uint256 amount) external returns (bool);
	function balanceOf(address account) external view returns (uint256);
	function allowance(address owner, address spender) external view returns (uint256);
}

contract DEX {

	IERC20 public token;
	address public owner;
	uint256 public constant TOKEN_PRICE = 1 ether / 1000; // 0.001 ETH za 1 token

	event Bought(address indexed buyer, uint256 amount);
	event Sold(address indexed seller, uint256 amount);

	modifier onlyOwner() {
		require(msg.sender == owner, "Tylko wlasciciel");
		_;
	}

	constructor(address _tokenAddress) {
		token = IERC20(_tokenAddress);
		owner = msg.sender;
	}

	function buy(uint256 _amount) external payable {
		uint256 cost = _amount * TOKEN_PRICE;
		require(msg.value == cost, "Nieprawidlowa kwota ETH");
		require(
			token.balanceOf(address(this)) >= _amount,
			"DEX nie ma wystarczajaco tokenow"
		);

		bool success = token.transfer(msg.sender, _amount);
		require(success, "Transfer tokenow nie powiodl sie");

		emit Bought(msg.sender, _amount);
	}

	function sell(uint256 _amount) external {
		require(
			token.balanceOf(msg.sender) >= _amount,
			"Uzytkownik nie ma wystarczajaco tokenow"
		);
		require(
			address(this).balance >= _amount * TOKEN_PRICE,
			"DEX nie ma wystarczajaco ETH"
		);

		// Pobranie tokenów od użytkownika (wymaga wcześniejszego approve)
		bool success = token.transferFrom(msg.sender, address(this), _amount);
		require(success, "TransferFrom nie powiodl sie");

		// Wypłata ETH użytkownikowi
		(bool sent, ) = payable(msg.sender).call{value: _amount * TOKEN_PRICE}("");
		require(sent, "Wyplata ETH nie powiodla sie");

		emit Sold(msg.sender, _amount);
	}

	function getAllowance(address _user) external view returns (uint256) {
		return token.allowance(_user, address(this));
	}

	function getEthBalance() external view returns (uint256) {
		return address(this).balance;
	}

	function depositTokens(uint256 _amount) external onlyOwner {
		bool success = token.transferFrom(msg.sender, address(this), _amount);
		require(success, "Depozyt tokenow nie powiodl sie");
	}

	function withdrawEth(uint256 _amount) external onlyOwner {
		require(address(this).balance >= _amount, "Za malo ETH");
		(bool sent, ) = payable(owner).call{value: _amount}("");
		require(sent, "Wyplata ETH nie powiodla sie");
	}

	receive() external payable {}
}
